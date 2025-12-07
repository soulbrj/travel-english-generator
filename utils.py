"""
工具函数模块
"""

import os
import json
import base64
from pathlib import Path
import pandas as pd
from datetime import datetime

class FileUtils:
    """文件操作工具类"""
    
    @staticmethod
    def ensure_directory(path):
        """确保目录存在"""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @staticmethod
    def save_dataframe(df, output_path, format='excel'):
        """保存DataFrame到文件"""
        try:
            output_path = Path(output_path)
            
            if format == 'excel':
                df.to_excel(output_path, index=False)
            elif format == 'csv':
                df.to_csv(output_path, index=False, encoding='utf-8-sig')
            elif format == 'json':
                df.to_json(output_path, orient='records', force_ascii=False, indent=2)
            else:
                raise ValueError(f"不支持的格式: {format}")
            
            return True
        except Exception as e:
            print(f"保存DataFrame失败: {e}")
            return False
    
    @staticmethod
    def load_dataframe(file_path, format=None):
        """从文件加载DataFrame"""
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                return None
            
            # 自动检测格式
            if format is None:
                suffix = file_path.suffix.lower()
                if suffix == '.xlsx' or suffix == '.xls':
                    format = 'excel'
                elif suffix == '.csv':
                    format = 'csv'
                elif suffix == '.json':
                    format = 'json'
                else:
                    format = 'excel'  # 默认
            
            if format == 'excel':
                df = pd.read_excel(file_path)
            elif format == 'csv':
                df = pd.read_csv(file_path, encoding='utf-8-sig')
            elif format == 'json':
                df = pd.read_json(file_path)
            else:
                raise ValueError(f"不支持的格式: {format}")
            
            return df
        except Exception as e:
            print(f"加载DataFrame失败: {e}")
            return None

class DataValidator:
    """数据验证工具类"""
    
    @staticmethod
    def validate_sentence_data(df):
        """验证句子数据"""
        result = {
            "is_valid": False,
            "errors": [],
            "warnings": [],
            "stats": {}
        }
        
        try:
            # 检查必需列
            required_columns = ["英语", "中文", "音标"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                result["errors"].append(f"缺少必需列: {missing_columns}")
            
            # 检查数据行数
            if len(df) == 0:
                result["errors"].append("数据为空")
            
            # 检查数据质量
            if "英语" in df.columns:
                # 检查英语列
                english_stats = {
                    "total": len(df["英语"]),
                    "empty": df["英语"].isna().sum()
                }
                
                if english_stats["empty"] > 0:
                    result["warnings"].append(f"有 {english_stats['empty']} 个英语句子为空")
            
            # 如果没有错误，标记为有效
            if not result["errors"]:
                result["is_valid"] = True
                
                # 添加统计信息
                result["stats"] = {
                    "total_sentences": len(df),
                    "columns": list(df.columns)
                }
            
            return result
            
        except Exception as e:
            result["errors"].append(f"验证过程中发生错误: {str(e)}")
            return result

class ExportUtils:
    """导出工具类"""
    
    @staticmethod
    def create_download_link(data, filename, mime_type=None):
        """创建下载链接"""
        if isinstance(data, pd.DataFrame):
            # 将DataFrame转换为CSV
            data = data.to_csv(index=False, encoding='utf-8-sig')
        
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        # Base64编码
        b64 = base64.b64encode(data).decode()
        
        # 确定MIME类型
        if mime_type is None:
            if filename.endswith('.csv'):
                mime_type = 'text/csv'
            elif filename.endswith('.json'):
                mime_type = 'application/json'
            elif filename.endswith('.xlsx'):
                mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            elif filename.endswith('.txt'):
                mime_type = 'text/plain'
            elif filename.endswith('.mp4'):
                mime_type = 'video/mp4'
            elif filename.endswith('.mp3'):
                mime_type = 'audio/mpeg'
            else:
                mime_type = 'application/octet-stream'
        
        href = f'<a href="data:{mime_type};base64,{b64}" download="{filename}">下载 {filename}</a>'
        return href

# 全局工具实例
file_utils = FileUtils()
data_validator = DataValidator()
export_utils = ExportUtils()