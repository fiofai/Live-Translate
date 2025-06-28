"""
简单的Web服务器，用于托管实时翻译客户端网页
修改版本适用于Render部署
"""

import os
import sys
import argparse
import threading
import time
import uuid
from flask import Flask, send_from_directory, redirect, url_for, jsonify, request
import qrcode
from PIL import Image
import io
import base64
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__, static_folder='web')

# 全局变量，用于存储翻译器实例
translator_instance = None
translator_thread = None

# 检查是否在Render环境中运行
is_render = 'RENDER' in os.environ

@app.route('/')
def index():
    """提供主页"""
    return send_from_directory('web', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    """提供静态文件"""
    return send_from_directory('web', path)

@app.route('/qrcode')
def show_qrcode():
    """显示二维码页面"""
    # 检查二维码文件是否存在
    if os.path.exists('translator_qrcode.png'):
        # 将二维码图像转换为base64
        with open('translator_qrcode.png', 'rb') as f:
            img_data = f.read()
        img_base64 = base64.b64encode(img_data).decode('utf-8')
        
        # 创建简单的HTML页面显示二维码
        html = f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>实时语音翻译 - 扫码连接</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                body {{ font-family: 'Microsoft YaHei', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
                .container {{ max-width: 500px; margin: 50px auto; text-align: center; }}
                .qrcode {{ margin: 20px 0; }}
                .qrcode img {{ max-width: 100%; height: auto; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>实时语音翻译</h2>
                <p class="text-muted">扫描下方二维码连接到翻译服务</p>
                <div class="qrcode">
                    <img src="data:image/png;base64,{img_base64}" alt="连接二维码">
                </div>
                <p>或直接访问以下链接：</p>
                <div class="d-grid gap-2">
                    <a href="/" class="btn btn-primary">打开翻译客户端</a>
                </div>
                <p class="mt-3">
                    <a href="/qrcode_image" target="_blank" class="btn btn-outline-secondary btn-sm">查看原始二维码图片</a>
                </p>
            </div>
        </body>
        </html>
        """
        return html
    else:
        # 二维码不存在，尝试启动翻译服务
        global translator_instance
        
        # 如果翻译服务没有运行，尝试启动它
        if translator_instance is None or not translator_instance.running:
            logger.info("二维码文件不存在，尝试启动翻译服务...")
            success = start_translator()
            
            if success:
                # 等待一段时间，让二维码生成
                time.sleep(3)
                
                # 检查二维码是否已生成
                if os.path.exists('translator_qrcode.png'):
                    # 重定向回二维码页面
                    return redirect(url_for('show_qrcode'))
                else:
                    # 手动生成二维码
                    try:
                        logger.info("尝试手动生成二维码...")
                        if translator_instance and hasattr(translator_instance, '_generate_qrcode'):
                            translator_instance._generate_qrcode()
                            return redirect(url_for('show_qrcode'))
                    except Exception as e:
                        logger.error(f"手动生成二维码失败: {e}")
        
        # 如果仍然无法生成二维码，显示错误消息和启动按钮
        html = """
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>实时语音翻译 - 二维码未生成</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                body { font-family: 'Microsoft YaHei', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
                .container { max-width: 500px; margin: 50px auto; text-align: center; }
            </style>
        </head>
        <body>
            <div class="container">
                <h2>实时语音翻译</h2>
                <div class="alert alert-warning" role="alert">
                    二维码尚未生成，请先启动翻译服务
                </div>
                <div class="d-grid gap-2">
                    <a href="/start_translator" class="btn btn-primary">启动翻译服务</a>
                </div>
                <p class="mt-3">
                    <a href="/qrcode" class="btn btn-outline-secondary btn-sm">刷新页面</a>
                </p>
            </div>
        </body>
        </html>
        """
        return html

@app.route('/qrcode_image')
def qrcode_image():
    """直接提供二维码图片"""
    if os.path.exists('translator_qrcode.png'):
        return send_from_directory(os.path.dirname(__file__), 'translator_qrcode.png')
    else:
        return "二维码图片不存在", 404

@app.route('/status')
def status():
    """返回服务状态"""
    global translator_instance
    
    status_info = {
        "server": "running",
        "translator": "running" if translator_instance and translator_instance.running else "not_running",
        "time": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    return jsonify(status_info)

@app.route('/upload_voice_sample', methods=['POST'])
def upload_voice_sample():
    """接收并保存语音样本文件，并启动语音克隆处理"""
    try:
        # 检查请求中是否包含文件
        if 'audio_file' not in request.files:
            return jsonify({"status": "error", "message": "没有找到音频文件"}), 400
        
        audio_file = request.files['audio_file']
        
        # 检查文件名是否为空
        if audio_file.filename == '':
            return jsonify({"status": "error", "message": "未选择文件"}), 400
        
        # 确保voice_samples目录存在
        voice_samples_dir = os.path.join(os.path.dirname(__file__), 'voice_samples')
        if not os.path.exists(voice_samples_dir):
            os.makedirs(voice_samples_dir)
            logger.info(f"创建目录: {voice_samples_dir}")
        
        # 生成用户ID（如果请求中没有提供）
        user_id = request.form.get('user_id', str(uuid.uuid4()))
        
        # 保存文件
        filename = os.path.join(voice_samples_dir, audio_file.filename)
        audio_file.save(filename)
        logger.info(f"保存语音样本: {filename}")
        
        # 在后台线程中处理语音样本
        def process_sample():
            try:
                try:
                    # 尝试从子模块导入
                    from clone_modules.voice_cloning.voice_clone_module import process_voice_sample
                    logger.info("从clone_modules.voice_cloning.voice_clone_module导入process_voice_sample成功")
                except ImportError:
                    # 如果失败，尝试从兼容层导入
                    try:
                        from voice_clone import process_voice_sample
                        logger.info("从voice_clone导入process_voice_sample成功")
                    except ImportError as e:
                        logger.error(f"导入process_voice_sample失败: {e}")
                        return
                
                logger.info(f"开始处理语音样本: {filename}, 用户ID: {user_id}")
                success = process_voice_sample(filename, user_id)
                if success:
                    logger.info(f"语音样本处理成功: {user_id}")
                else:
                    logger.error(f"语音样本处理失败: {user_id}")
            except Exception as e:
                logger.error(f"处理语音样本时出错: {e}")
        
        # 启动处理线程
        processing_thread = threading.Thread(target=process_sample)
        processing_thread.daemon = True
        processing_thread.start()
        
        # 返回成功响应
        return jsonify({
            "status": "success", 
            "message": "语音样本已上传，正在处理中",
            "filename": audio_file.filename,
            "speaker_id": user_id
        })
    
    except Exception as e:
        logger.error(f"上传语音样本失败: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/clone_status', methods=['GET'])
def clone_status():
    """查询语音克隆处理状态"""
    try:
        # 获取用户ID
        user_id = request.args.get('speaker_id')
        if not user_id:
            return jsonify({"status": "error", "message": "未提供speaker_id参数"}), 400
        
        # 查询处理状态
        try:
            # 尝试从子模块导入
            from clone_modules.voice_cloning.voice_clone_module import get_processing_status
            logger.info("从clone_modules.voice_cloning.voice_clone_module导入get_processing_status成功")
        except ImportError:
            # 如果失败，尝试从兼容层导入
            try:
                from voice_clone import get_processing_status
                logger.info("从voice_clone导入get_processing_status成功")
            except ImportError as e:
                logger.error(f"导入get_processing_status失败: {e}")
                return jsonify({"status": "error", "message": "语音克隆模块未正确加载"}), 500
        
        # 获取处理状态
        status_info = get_processing_status(user_id)
        return jsonify(status_info)
    
    except Exception as e:
        logger.error(f"查询语音克隆处理状态失败: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/start_translator')
def start_translator_endpoint():
    """API端点，用于启动翻译服务"""
    global translator_instance, translator_thread
    
    if translator_instance is None or not translator_instance.running:
        try:
            success = start_translator()
            if success:
                # 等待一段时间，让二维码生成
                time.sleep(3)
                
                # 检查二维码是否已生成
                if os.path.exists('translator_qrcode.png'):
                    return redirect(url_for('show_qrcode'))
                else:
                    return jsonify({"status": "success", "message": "翻译服务已启动，请刷新二维码页面"})
            else:
                return jsonify({"status": "error", "message": "启动翻译服务失败"}), 500
        except Exception as e:
            logger.error(f"启动翻译服务失败: {e}")
            return jsonify({"status": "error", "message": f"启动失败: {str(e)}"}), 500
    else:
        return redirect(url_for('show_qrcode'))

def start_translator():
    """启动翻译服务"""
    global translator_instance, translator_thread
    
    try:
        from main import LiveTranslator
        
        # 创建并启动翻译系统（使用模拟音频）
        translator_instance = LiveTranslator(
            use_faster_whisper=True,
            use_google_translate=True,
            whisper_model="small",  # 使用较小的模型以适应云环境的资源限制
            room_name="live-translator",
            use_simulation=True     # 在云环境上使用模拟音频
        )
        
        # 在单独的线程中启动翻译服务
        def run_translator():
            try:
                translator_instance.start()
                logger.info("翻译服务已启动")
            except Exception as e:
                logger.error(f"翻译服务出错: {e}")
        
        translator_thread = threading.Thread(target=run_translator)
        translator_thread.daemon = True
        translator_thread.start()
        
        logger.info("翻译服务线程已启动")
        return True
    except Exception as e:
        logger.error(f"导入或启动翻译服务时出错: {e}")
        return False

def start_server(host='0.0.0.0', port=8080, with_translator=False):
    """启动Web服务器"""
    # 使用环境变量中的端口（Render会设置PORT环境变量）
    port = int(os.environ.get('PORT', port))
    
    logger.info(f"Web服务器已启动：http://{host}:{port}")
    logger.info(f"二维码页面：http://{host}:{port}/qrcode")
    
    if with_translator:
        # 尝试启动翻译服务
        try:
            success = start_translator()
            if success:
                logger.info("翻译服务已在Web服务器启动过程中自动启动")
            else:
                logger.warning("翻译服务未能自动启动，可以稍后通过API启动")
        except Exception as e:
            logger.error(f"启动翻译服务时出错: {e}")
    
    # 检查是否在云环境中运行
    if not is_render:
        # 仅在本地运行时使用app.run()
        app.run(host=host, port=port, debug=False)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="实时翻译Web服务器")
    parser.add_argument("--host", default="0.0.0.0", help="服务器主机（默认：0.0.0.0）")
    parser.add_argument("--port", type=int, default=8080, help="服务器端口（默认：8080）")
    parser.add_argument("--with-translator", action="store_true", help="自动启动翻译服务")
    args = parser.parse_args()
    
    start_server(host=args.host, port=args.port, with_translator=args.with_translator) 