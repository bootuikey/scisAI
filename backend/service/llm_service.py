import os
import google.generativeai as genai
from typing import List
import json
from PIL import Image
from schema.api_schema import Suggestion, AnalysisResult

class LLMService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            # For now, we allow init without key, but check later
            pass
        else:
            genai.configure(api_key=api_key)
            
    def analyze_content(self, text: str, figures: List[Image.Image], formulas: List[Image.Image], tables: List[Image.Image], filename: str) -> AnalysisResult:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
             raise Exception("GEMINI_API_KEY environment variable not found.")
        
        model = genai.GenerativeModel('gemini-3-flash-preview')
        
        prompt_intro = f"""
        你是一位严谨的SCI学术期刊编辑。请对提供的PDF内容（文本、插图、公式截图）进行全面审查。
        
        任务说明：
        任务说明：
        请结合以下四个部分的内容进行分析：
        """

        prompt_text = f"""
        **第一部分：文本分析**
        待分析文本片段:
        {text[:50000]}
        
        要求：
        - 检查行文是否清晰流畅。
        - 检查是否存在拼写错误、语法错误或表达不当之处。
        """

        prompt_figures = """
        **第二部分：插图与图表分析**（请参考后续附带的【插图图片】）
        要求：
        - **视觉扫描**：请仔细扫描每一个插图、照片或统计图表。
        - **版权隐私（高优先级）**：若图片中包含人物肖像（Portrait）、电影剧照、知名商标或商业宣传图，**必须**在建议中明确指出“该图片可能涉及版权或肖像权问题，需确认是否已获得授权”。
        - **颜色检查**：检查图中的文字和线条是否使用了**浅色**（如黄色、淡蓝色、淡绿色等），这可能会导致打印不清。如果发现，请作为“compliance_warning”提出。
        - **格式规范**：检查图例（Legend）或标题（Caption），短语仅首个单词首字母大写；若是完整句子，需符合英文书写规范（首字母大写，结尾标点）。
        - **数据图表**：对于数据图（Data Chart），检查横纵坐标是否有明确的变量名（Label）或单位（Unit）。
        """

        prompt_formulas = """
        **第三部分：公式分析**（请参考后续附带的【公式截图】）
        要求：
        - 对于每一个公式截图，请在内部尝试将其转换为 **LaTeX** 形式以辅助理解（不需要在JSON中输出LaTeX，仅作为你检查的中间步骤）。
        - **标点符号**：原则上不允许出现没有标点符号的公式行。请检查公式末尾是否根据行文情况使用了正确的标点（如“,”或“.”）。
        - **符号一致性**：检查公式中的符号与正文、图片/图表中的符号格式是否一致。
          - 例如：变量通常应为textit（斜体），矢量通常为bold（粗体）。
          - 检查上下角标是否统一。
        """

        prompt_tables = """
        **第四部分：表格分析**（请参考后续附带的【表格截图】）
        要求：
        - **彩色内容检查**：严格检查表格中的文字、线条或背景是否使用了**彩色**（非黑白灰）。表格内容（包括表头、数据、边框）原则上应为黑白或灰度。如果发现彩色，请务必提出警示。
        - **浅色内容检查**：检查表格中是否存在**浅色**（如黄色、淡蓝色）的文字或线条，这种颜色打印时极难辨认。
        """

        prompt_json = """
        请严格按照以下JSON格式返回结果。
        **重要：所有与建议相关的内容（description, suggestion, etc.）必须使用简体中文。**
        **注意：JSON字符串中如果包含反斜杠（\\），必须进行转义（即写成 \\\\）。**

        参考JSON结构：
        {{
            "suggestions": [
                {{
                    "original_text": "原文片段、图片描述或公式位置（例如：'图2' 或 '公式截图3'）",
                    "issue_type": "错误类型（语法/拼写/公式规范/符号一致性/图表规范/版权隐私/其他）",
                    "description": "详细的问题描述（简体中文）",
                    "suggestion": "具体的修改建议（简体中文）"
                }}
            ],
            "general_comments": "对稿件的整体评价和修改建议（简体中文）"
        }}
        """
        
        try:
            # Construct the complex multimodal payload
            content_payload = [prompt_intro, prompt_text, prompt_figures, prompt_formulas, prompt_tables, prompt_json]
            
            # Append Figures
            if figures:
                content_payload.append("\n\n【以下是提取的插图/图片】：")
                # Limit to first 15 figures to avoid overload
                content_payload.extend(figures[:15])
            else:
                content_payload.append("\n\n(未提取到插图)")

            # Append Formulas
            if formulas:
                content_payload.append("\n\n【以下是提取的公式截图】：")
                # Limit to first 100 formulas (formulas are small)
                content_payload.extend(formulas[:100])
            else:
                content_payload.append("\n\n(未检测到独立公式块)")

            # Append Tables
            if tables:
                content_payload.append("\n\n【以下是提取的表格截图】：")
                # Limit to first 20 tables
                content_payload.extend(tables[:20])
            else:
                content_payload.append("\n\n(未检测到表格)")

            response = model.generate_content(
                content_payload,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.0
                )
            )
            
            # Cleanup potential markdown ticks
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            
            try:
                result_dict = json.loads(clean_text)
            except json.JSONDecodeError:
                # Fallback: Try to fix escaped backslashes
                try:
                    clean_text_fixed = clean_text.replace("\\", "\\\\") 
                    result_dict = json.loads(clean_text_fixed)
                except:
                    print(f"JSON Parse Error. Raw Text: {clean_text}")
                    raise 
            
            suggestions = []
            for item in result_dict.get("suggestions", []):
                suggestions.append(Suggestion(**item))
                
            return AnalysisResult(
                filename=filename,
                suggestions=suggestions,
                general_comments=result_dict.get("general_comments", "")
            )
            
        except Exception as e:
             # Fallback or error handling
             print(f"LLM Error Details: {e}")
             raise Exception(f"Failed to analyze text with Gemini: {str(e)}")

llm_service = LLMService()
