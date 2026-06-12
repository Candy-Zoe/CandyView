"""
PDF文档生成器 - 将提取的帧和分析结果生成PDF文档
使用reportlab直接生成，无需依赖Word
"""

import os
import io
import tempfile
from PIL import Image

try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import inch, cm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
        Table, TableStyle, PageBreak, KeepTogether
    )
    from reportlab.pdfgen import canvas
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    _HAS_REPORTLAB = True
except ImportError:
    _HAS_REPORTLAB = False


# 预设PDF样式
PDF_THEMES = {
    'professional': {
        'name': '专业商务',
        'title_color': colors.HexColor('#1F497D'),
        'heading_color': colors.HexColor('#004AA6'),
        'text_color': colors.black,
        'accent_color': colors.HexColor('#1F497D'),
        'bg_color': colors.HexColor('#F5F5F5'),
    },
    'modern': {
        'name': '现代简约',
        'title_color': colors.HexColor('#333333'),
        'heading_color': colors.HexColor('#0070C0'),
        'text_color': colors.HexColor('#595959'),
        'accent_color': colors.HexColor('#0070C0'),
        'bg_color': colors.white,
    },
    'minimal': {
        'name': '极简白',
        'title_color': colors.black,
        'heading_color': colors.HexColor('#333333'),
        'text_color': colors.HexColor('#555555'),
        'accent_color': colors.HexColor('#888888'),
        'bg_color': colors.white,
    },
    'dark': {
        'name': '深色主题',
        'title_color': colors.white,
        'heading_color': colors.HexColor('#6699FF'),
        'text_color': colors.HexColor('#DDDDDD'),
        'accent_color': colors.HexColor('#66CCFF'),
        'bg_color': colors.HexColor('#2B2B2B'),
    },
}


class PDFGenerator:
    def __init__(self, theme='modern', title='视频要点提取', subtitle=''):
        if not _HAS_REPORTLAB:
            raise RuntimeError("请先安装 reportlab: pip install reportlab")
        self.theme_name = theme
        self.theme = PDF_THEMES.get(theme, PDF_THEMES['modern'])
        self.title_text = title
        self.subtitle_text = subtitle
        self.story = []
        self._setup_styles()

    def _setup_styles(self):
        """设置文档样式"""
        self.styles = getSampleStyleSheet()

        # 自定义标题样式
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            fontName='Helvetica-Bold',
            fontSize=28,
            textColor=self.theme['title_color'],
            alignment=TA_CENTER,
            spaceAfter=20,
        ))

        # 自定义副标题样式
        self.styles.add(ParagraphStyle(
            name='CustomSubtitle',
            fontName='Helvetica',
            fontSize=16,
            textColor=self.theme['accent_color'],
            alignment=TA_CENTER,
            spaceAfter=30,
        ))

        # 自定义页面标题样式
        self.styles.add(ParagraphStyle(
            name='PageHeading',
            fontName='Helvetica-Bold',
            fontSize=18,
            textColor=self.theme['heading_color'],
            alignment=TA_LEFT,
            spaceAfter=12,
            spaceBefore=6,
        ))

        # 自定义正文样式
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            fontName='Helvetica',
            fontSize=11,
            textColor=self.theme['text_color'],
            alignment=TA_LEFT,
            leading=16,
            spaceAfter=8,
        ))

        # 自定义要点样式
        self.styles.add(ParagraphStyle(
            name='BulletPoint',
            fontName='Helvetica',
            fontSize=11,
            textColor=self.theme['text_color'],
            alignment=TA_LEFT,
            leftIndent=20,
            leading=16,
            spaceAfter=6,
        ))

        # 底部信息样式
        self.styles.add(ParagraphStyle(
            name='Footer',
            fontName='Helvetica',
            fontSize=9,
            textColor=colors.HexColor('#888888'),
            alignment=TA_CENTER,
        ))

    def _hex_to_rgb(self, hex_str):
        """HEX颜色转RGB"""
        hex_str = hex_str.lstrip('#')
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

    def add_title_page(self):
        """添加封面"""
        self.story.append(Spacer(1, 2 * inch))
        self.story.append(Paragraph(self.title_text, self.styles['CustomTitle']))
        self.story.append(Paragraph(self.subtitle_text, self.styles['CustomSubtitle']))
        self.story.append(Spacer(1, 2 * inch))

        # 尝试使用中文字体
        footer_style = ParagraphStyle(
            name='FooterCustom',
            fontName='Helvetica',
            fontSize=10,
            textColor=colors.HexColor('#888888'),
            alignment=TA_CENTER,
        )
        self.story.append(Paragraph('VideoToPPT · 自动生成', footer_style))
        self.story.append(PageBreak())

    def add_page(self, img_rgb, title, bullet_points=None,
                 include_image=True, image_position='right'):
        """
        添加一页内容

        参数:
            img_rgb: numpy.ndarray (H, W, 3) RGB
            title: 页面标题
            bullet_points: list[str] 要点列表
            include_image: 是否包含截图
            image_position: 'right' | 'left' | 'below'  图片位置
        """
        # 分隔线
        self.story.append(Spacer(1, 0.3 * cm))

        # 标题
        self.story.append(Paragraph(title, self.styles['PageHeading']))

        if include_image:
            # 将numpy图像转为PIL再转reportlab可用格式
            pil_img = Image.fromarray(img_rgb)
            img_buffer = io.BytesIO()
            pil_img.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            rl_img = RLImage(img_buffer)

            if image_position == 'below':
                # 图片在下
                if bullet_points:
                    for bp in bullet_points:
                        if bp.strip():
                            self.story.append(Paragraph(f"• {bp.strip()}", self.styles['BulletPoint']))
                    self.story.append(Spacer(1, 0.3 * cm))

                # 图片居中显示
                img_table = Table([[rl_img]], colWidths=[5 * inch])
                img_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
                self.story.append(img_table)
            else:
                # 图文左右并排
                # 文字部分
                text_content = []
                if bullet_points:
                    for bp in bullet_points:
                        if bp.strip():
                            text_content.append(Paragraph(f"• {bp.strip()}", self.styles['BulletPoint']))
                else:
                    text_content.append(Paragraph("（无文本内容）", ParagraphStyle(
                        name='ItalicHint',
                        fontName='Helvetica-Oblique',
                        fontSize=10,
                        textColor=colors.HexColor('#888888'),
                    )))

                # 图片缩放
                img_width = 4.5 * inch
                aspect = pil_img.height / pil_img.width
                img_height = img_width * aspect

                rl_img_draw = RLImage(img_buffer, width=img_width, height=img_height)
                img_para = Paragraph('', self.styles['CustomBody'])
                img_table = Table([[img_para, rl_img_draw]], colWidths=[4.5 * inch, 4.5 * inch])

                if image_position == 'left':
                    img_table = Table([[rl_img_draw, img_para]], colWidths=[4.5 * inch, 4.5 * inch])

                # 构建完整内容表格
                text_cell = text_content
                img_cell = Table([[rl_img_draw]], colWidths=[img_width])
                img_cell.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ]))

                if image_position == 'left':
                    main_table = Table([[img_cell, text_cell]], colWidths=[4.5 * inch, 4.5 * inch])
                else:
                    main_table = Table([[text_cell, img_cell]], colWidths=[4.5 * inch, 4.5 * inch])

                main_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                    ('TOPPADDING', (0, 0), (-1, -1), 0),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                ]))

                self.story.append(main_table)
        else:
            # 仅文字
            if bullet_points:
                for bp in bullet_points:
                    if bp.strip():
                        self.story.append(Paragraph(f"• {bp.strip()}", self.styles['BulletPoint']))
            else:
                self.story.append(Paragraph("（无文本内容）", ParagraphStyle(
                    name='ItalicHint2',
                    fontName='Helvetica-Oblique',
                    fontSize=10,
                    textColor=colors.HexColor('#888888'),
                )))

        self.story.append(Spacer(1, 0.5 * cm))
        self.story.append(PageBreak())

    def save(self, output_path):
        """保存PDF文档"""
        # 创建横向A4文档
        page_width, page_height = landscape(A4)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=landscape(A4),
            leftMargin=1 * cm,
            rightMargin=1 * cm,
            topMargin=1 * cm,
            bottomMargin=1 * cm,
        )

        doc.build(self.story)
        return output_path


class PDFGeneratorCanvas(PDFGenerator):
    """
    使用Canvas API的PDF生成器 - 更底层的控制
    支持更复杂的自定义布局
    """

    def add_custom_page(self, img_rgb, title, bullet_points=None,
                       include_image=True, page_num=1, total_pages=1):
        """添加自定义布局页面"""
        pass  # 暂时不使用，更复杂的自定义页面可以后续扩展


def build_pdf(frames_with_analysis, output_path,
              theme='modern',
              title='视频要点',
              subtitle='由 VideoToPPT 自动生成',
              image_position='right',
              include_ocr=True,
              progress_callback=None):
    """
    从分析结果构建完整PDF文档

    参数:
        frames_with_analysis: list[dict]
        output_path: 输出文件路径
        theme: 主题名
        image_position: 'right' | 'left' | 'below'
        include_ocr: 是否包含OCR文本
        progress_callback: 进度回调
    """
    gen = PDFGenerator(theme=theme, title=title, subtitle=subtitle)
    gen.add_title_page()

    total = len(frames_with_analysis)
    for i, item in enumerate(frames_with_analysis):
        img = item.get('image')
        analysis = item.get('analysis', {})
        title_txt = analysis.get('title') or analysis.get('auto_title') or f"幻灯片 {i + 1}"

        bullets = []
        if include_ocr and analysis.get('bullet_points'):
            bullets = analysis['bullet_points']
        elif include_ocr and analysis.get('content'):
            bullets = [b for b in analysis['content'].split('\n') if b.strip()]

        gen.add_page(
            img_rgb=img,
            title=title_txt,
            bullet_points=bullets,
            include_image=True,
            image_position=image_position,
        )

        if progress_callback:
            percent = int(50 + 50.0 * (i + 1) / max(total, 1))
            progress_callback(percent, f"生成第 {i + 1}/{total} 页...")

    gen.save(output_path)
    return output_path
