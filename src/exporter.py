"""
模块 6: Exporter（导出器 — MVP 版本）

职责：
- 将 composed_video.mp4 复制/重命名为规范文件名
- 输出 metadata.json
- 可选清理临时文件
"""

import json
import shutil
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from src.utils import ensure_dir


# ── Data Models ──────────────────────────────────────────

class ExportResult(BaseModel):
    """导出结果"""
    video_path: Path
    metadata_path: Path
    file_size_mb: float


# ── Exporter ─────────────────────────────────────────────

class Exporter:
    """
    视频导出器。

    Attributes:
        output_dir: 最终输出目录
        temp_dir: 临时文件目录
        cleanup: 是否清理临时文件
    """

    def __init__(self, output_dir: Path, temp_dir: Path, cleanup: bool = True):
        """
        Args:
            output_dir: 最终输出目录
            temp_dir: 临时文件目录
            cleanup: 导出后是否清理 temp/
        """
        self.output_dir = output_dir
        self.temp_dir = temp_dir
        self.cleanup = cleanup
        ensure_dir(self.output_dir)

    # ── Public API ───────────────────────────────────────

    def export(
        self,
        composed_video_path: Path,
        topic: str,
        metadata: dict,
    ) -> ExportResult:
        """
        导出最终视频和元数据。

        流程：
            1. 生成规范文件名：{topic}_{date}.mp4
            2. 复制视频到 output/
            3. 写入 metadata.json
            4. 可选清理 temp/

        Args:
            composed_video_path: 合成后的视频路径
            topic: 原始主题（用于命名）
            metadata: 生成元数据

        Returns:
            ExportResult（最终视频路径 + 元数据）

        Raises:
            FileNotFoundError: 合成视频不存在
            RuntimeError: 导出失败
        """
        if not composed_video_path.exists():
            raise FileNotFoundError(f"合成视频不存在: {composed_video_path}")

        safe_topic = self._sanitize_filename(topic)
        date_str = datetime.now().strftime("%Y%m%d")

        # 1. 复制视频到最终位置
        video_name = f"{safe_topic}_{date_str}.mp4"
        final_video = self.output_dir / video_name
        shutil.copy2(composed_video_path, final_video)

        # 2. 计算文件大小
        file_size_mb = round(final_video.stat().st_size / (1024 * 1024), 2)

        # 3. 写入 metadata.json
        meta_name = f"{safe_topic}_{date_str}.json"
        meta_path = self.output_dir / meta_name
        meta_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 4. 可选清理
        if self.cleanup:
            self._clean_temp()

        print(f"  [Exporter] [OK] 导出完成: {final_video}")
        print(f"  [Exporter] [OK] 大小: {file_size_mb} MB")
        print(f"  [Exporter] [OK] 元数据: {meta_path}")

        return ExportResult(
            video_path=final_video,
            metadata_path=meta_path,
            file_size_mb=file_size_mb,
        )

    # ── Private ───────────────────────────────────────────

    def _sanitize_filename(self, topic: str) -> str:
        """
        将主题转换为安全的文件名。

        Args:
            topic: 如 "沙巴5天4晚旅游攻略"

        Returns:
            安全文件名，如 "沙巴5天4晚旅游攻略"
        """
        # 去除路径不安全字符
        unsafe_chars = r'[<>:"/\\|?*]'
        safe = topic.strip()
        for ch in ['<', '>', ':', '"', '/', '\\', '|', '?', '*']:
            safe = safe.replace(ch, "_")
        # 限制长度
        if len(safe) > 50:
            safe = safe[:50]
        return safe

    def _clean_temp(self) -> None:
        """清理临时文件目录。"""
        if self.temp_dir.exists():
            for item in self.temp_dir.iterdir():
                if item.name == ".gitkeep":
                    continue
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
