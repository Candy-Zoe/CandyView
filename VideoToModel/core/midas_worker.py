"""
MiDaS深度学习工作进程
独立进程运行，避免与PyQt5的DLL冲突
"""

import sys
import numpy as np
import json
import base64
import io


def run_midas_estimation(image_data, model_name="intel/dpt-hybrid-midas"):
    """运行MiDaS深度估计"""
    try:
        import torch
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation
        from PIL import Image
        
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"[MiDaS] 使用设备: {device}", flush=True)
        
        processor = AutoImageProcessor.from_pretrained(model_name)
        model = AutoModelForDepthEstimation.from_pretrained(model_name)
        model.to(device)
        model.eval()
        
        image = Image.open(io.BytesIO(image_data))
        input_tensor = processor(images=image, return_tensors="pt").to(device)
        
        with torch.no_grad():
            outputs = model(**input_tensor)
            predicted_depth = outputs.predicted_depth
        
        depth = torch.nn.functional.interpolate(
            predicted_depth.unsqueeze(1),
            size=image.size[::-1],
            mode="bicubic",
            align_corners=False,
        ).squeeze().cpu().numpy()
        
        depth = (depth - depth.min()) / (depth.max() - depth.min() + 1e-10)
        
        return {
            'success': True,
            'depth': depth.tolist(),
            'device': device
        }
    except Exception as e:
        import traceback
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }


def main():
    if len(sys.argv) < 2:
        print(json.dumps({'success': False, 'error': 'No input data'}))
        return
    
    try:
        encoded_data = sys.argv[1]
        image_data = base64.b64decode(encoded_data)
        result = run_midas_estimation(image_data)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({'success': False, 'error': str(e)}))


if __name__ == "__main__":
    main()
