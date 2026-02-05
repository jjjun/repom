"""Display repom configuration information."""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from repom.config import config
from repom.database import get_sync_engine, Base
from repom._.discovery import import_from_packages


def format_size(size_bytes: int) -> str:
    """Format file size in MB.

    Args:
        size_bytes: File size in bytes

    Returns:
        Formatted size string (e.g., "2.50 MB")
    """
    return f"{size_bytes / (1024 * 1024):.2f} MB"


def get_db_file_info() -> Optional[Dict[str, any]]:
    """Get SQLite database file information.

    Returns:
        Dictionary with file_path, exists, and size_mb, or None if not SQLite
    """
    if config.db_type != 'sqlite':
        return None

    # Extract file path from db_url (e.g., "sqlite:///data/repom/db.dev.sqlite3")
    db_url = str(config.db_url)
    if db_url.startswith('sqlite:///:memory:'):
        return {
            'file_path': ':memory:',
            'exists': True,
            'size_mb': 'N/A (in-memory)'
        }
    elif db_url.startswith('sqlite:///'):
        file_path = db_url.replace('sqlite:///', '', 1)
    else:
        return None

    # Convert to absolute path
    if not Path(file_path).is_absolute():
        file_path = config.root_path / file_path
    else:
        file_path = Path(file_path)

    exists = file_path.exists()
    size_mb = format_size(file_path.stat().st_size) if exists else 'N/A'

    return {
        'file_path': str(file_path),
        'exists': exists,
        'size_mb': size_mb
    }


def parse_postgres_url(db_url: str) -> Optional[Dict[str, str]]:
    """Parse PostgreSQL connection URL.

    Args:
        db_url: PostgreSQL connection URL

    Returns:
        Dictionary with host, port, database, and user
    """
    if not db_url.startswith('postgresql'):
        return None

    # Example: postgresql://user:password@localhost:5432/dbname
    try:
        # Remove password for security
        url = db_url.split('://', 1)[1]  # Remove scheme
        if '@' in url:
            credentials, rest = url.split('@', 1)
            user = credentials.split(':', 1)[0]  # Get user, ignore password
        else:
            user = 'N/A'
            rest = url

        if '/' in rest:
            host_port, database = rest.split('/', 1)
        else:
            host_port = rest
            database = 'N/A'

        if ':' in host_port:
            host, port = host_port.split(':', 1)
        else:
            host = host_port
            port = '5432'

        return {
            'host': host,
            'port': port,
            'database': database,
            'user': user
        }
    except Exception:
        return None


def test_postgres_connection() -> str:
    """Test PostgreSQL connection.

    Returns:
        Connection test result string
    """
    if config.db_type != 'postgresql':
        return '(Not applicable for SQLite)'

    try:
        engine = get_sync_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return '✓ Connected'
    except SQLAlchemyError as e:
        return f'✗ Failed: {str(e)[:50]}'
    except Exception as e:
        return f'✗ Error: {str(e)[:50]}'


def get_loaded_models() -> List[Dict[str, str]]:
    """Get list of loaded models from SQLAlchemy metadata.

    Returns:
        List of dictionaries with model_name, table_name, and package
    """
    models = []

    # Auto-import models if configured
    if config.model_locations:
        try:
            import_from_packages(
                package_names=config.model_locations,
                excluded_dirs=config.model_excluded_dirs,
                allowed_prefixes=config.allowed_package_prefixes
            )
        except Exception:
            pass  # Silently continue if import fails

    # Get all tables from metadata
    for table_name, table in Base.metadata.tables.items():
        # Try to find the model class
        model_class = None
        for mapper in Base.registry.mappers:
            if mapper.mapped_table.name == table_name:
                model_class = mapper.class_
                break

        if model_class:
            models.append({
                'model_name': model_class.__name__,
                'table_name': table_name,
                'package': f"{model_class.__module__}.{model_class.__name__}"
            })
        else:
            # Fallback if model class not found
            models.append({
                'model_name': table_name,
                'table_name': table_name,
                'package': 'Unknown'
            })

    return sorted(models, key=lambda x: x['model_name'])


def display_config():
    """Display repom configuration information."""

    print("=" * 60)
    print("repom Configuration Information")
    print("=" * 60)
    print()

    # Basic Paths
    print("[Basic Paths]")
    print(f"  Root Path         : {config.root_path}")
    print(f"  Backup Path       : {config.db_backup_path}")
    print(f"  Master Data Path  : {config.master_data_path}")
    print()

    # Database Configuration
    print("[Database Configuration]")
    print(f"  Type              : {config.db_type}")

    # Mask password in URL
    db_url_display = str(config.db_url)
    if '@' in db_url_display and '://' in db_url_display:
        scheme, rest = db_url_display.split('://', 1)
        if '@' in rest:
            credentials, host_part = rest.split('@', 1)
            if ':' in credentials:
                user, _ = credentials.split(':', 1)
                db_url_display = f"{scheme}://{user}:***@{host_part}"

    print(f"  URL               : {db_url_display}")
    print()

    # Database-specific details
    if config.db_type == 'sqlite':
        db_info = get_db_file_info()
        if db_info:
            print("  [SQLite Details]")
            print(f"    File Path       : {db_info['file_path']}")
            print(f"    File Exists     : {'Yes' if db_info['exists'] else 'No'}")
            print(f"    File Size       : {db_info['size_mb']}")
            print()

    elif config.db_type == 'postgresql':
        pg_info = parse_postgres_url(str(config.db_url))
        if pg_info:
            print("  [PostgreSQL Details]")
            print(f"    Host            : {pg_info['host']}")
            print(f"    Port            : {pg_info['port']}")
            print(f"    Database        : {pg_info['database']}")
            print(f"    User            : {pg_info['user']}")
            print()

    # PostgreSQL Connection Test
    print("[PostgreSQL Connection Test]")
    connection_status = test_postgres_connection()
    print(f"  Status            : {connection_status}")
    print()

    # Model Loading Configuration
    print("[Model Loading Configuration]")
    print(f"  Model Locations   : {config.model_locations}")
    print(f"  Allowed Prefixes  : {config.allowed_package_prefixes}")
    print(f"  Excluded Dirs     : {config.model_excluded_dirs}")
    print()

    # Loaded Models
    models = get_loaded_models()
    print(f"  [Loaded Models] ({len(models)} model{'s' if len(models) != 1 else ''} found)")

    if models:
        for idx, model in enumerate(models, 1):
            print(f"    {idx}. {model['model_name']}")
            print(f"       - Table      : {model['table_name']}")
            print(f"       - Package    : {model['package']}")
    else:
        print("    (No models loaded)")
    print()

    # Environment
    print("[Environment]")
    exec_env = os.getenv('EXEC_ENV', 'dev')
    config_hook = os.getenv('CONFIG_HOOK', 'Not set')
    print(f"  EXEC_ENV          : {exec_env}")
    print(f"  CONFIG_HOOK       : {config_hook}")
    print()

    print("=" * 60)


def main():
    """Main entry point for the script."""
    try:
        display_config()
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
