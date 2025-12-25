from sqlalchemy import String, Date
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, date
from typing import Optional

from repom.base_model_auto import BaseModelAuto
from repom.utility import get_plural_tablename


class SampleModel(BaseModelAuto, use_id=True, use_created_at=True, use_updated_at=True):
    """サンプルモデル
    
    推奨構造:
    - BaseModelAuto を継承（Pydantic スキーマ自動生成機能）
    - パラメータ方式で use_* フラグを指定
    - info メタデータで description を記述
    """
    __tablename__ = get_plural_tablename(__file__)

    value: Mapped[str] = mapped_column(
        String(255), 
        nullable=False, 
        default='',
        info={'description': 'サンプル値（最大5０文字）'}
    )
    done_at: Mapped[Optional[date]] = mapped_column(
        Date,
        info={'description': '完了日'}
    )

    def done(self):
        """
        done_atに今日の日付を代入する関数
        """
        self.done_at = datetime.now().date()
        return self
