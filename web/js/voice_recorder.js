/**
 * 语音克隆录音功能
 * 实现浏览器录音和上传到Flask后端的功能
 */

document.addEventListener('DOMContentLoaded', () => {
    // 获取DOM元素
    const startRecordBtn = document.getElementById('start-record');
    const stopRecordBtn = document.getElementById('stop-record');
    const recordingStatus = document.getElementById('recording-status');
    const audioContainer = document.getElementById('audio-container');
    const recordedAudio = document.getElementById('recorded-audio');
    const uploadStatus = document.getElementById('upload-status');
    
    // 录音相关变量
    let mediaRecorder;
    let audioChunks = [];
    let audioBlob;
    let audioUrl;
    let currentSpeakerId = localStorage.getItem('voiceSampleSpeakerId');
    let statusCheckInterval = null;
    
    // 检查浏览器是否支持录音API
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        recordingStatus.textContent = '您的浏览器不支持录音功能，请使用Chrome或Edge浏览器。';
        startRecordBtn.disabled = true;
        return;
    }
    
    // 如果已经有保存的speaker_id，检查其状态
    if (currentSpeakerId) {
        checkCloneStatus(currentSpeakerId);
    }
    
    // 开始录音
    startRecordBtn.addEventListener('click', async () => {
        try {
            // 请求麦克风权限
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            
            // 创建MediaRecorder实例
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            
            // 收集录音数据
            mediaRecorder.addEventListener('dataavailable', event => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            });
            
            // 录音结束后处理
            mediaRecorder.addEventListener('stop', () => {
                // 创建音频Blob
                audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                
                // 创建音频URL并设置到audio元素
                if (audioUrl) {
                    URL.revokeObjectURL(audioUrl); // 释放旧的URL
                }
                audioUrl = URL.createObjectURL(audioBlob);
                recordedAudio.src = audioUrl;
                
                // 显示音频播放器
                audioContainer.style.display = 'block';
                
                // 自动上传录音
                uploadRecording();
                
                // 停止所有音轨
                stream.getTracks().forEach(track => track.stop());
            });
            
            // 开始录音
            mediaRecorder.start();
            
            // 更新UI状态
            startRecordBtn.disabled = true;
            stopRecordBtn.disabled = false;
            recordingStatus.textContent = '正在录音...';
            recordingStatus.style.color = '#dc3545';
            
        } catch (error) {
            console.error('录音失败:', error);
            recordingStatus.textContent = '无法访问麦克风，请确保已授予权限。';
        }
    });
    
    // 停止录音
    stopRecordBtn.addEventListener('click', () => {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
            
            // 更新UI状态
            startRecordBtn.disabled = false;
            stopRecordBtn.disabled = true;
            recordingStatus.textContent = '录音已完成';
            recordingStatus.style.color = '#198754';
        }
    });
    
    // 上传录音到服务器
    function uploadRecording() {
        if (!audioBlob) {
            uploadStatus.textContent = '没有可上传的录音';
            return;
        }
        
        // 创建FormData对象
        const formData = new FormData();
        
        // 使用当前时间戳作为文件名，确保唯一性
        const fileName = `voice_sample_${Date.now()}.webm`;
        formData.append('audio_file', audioBlob, fileName);
        
        // 更新上传状态
        uploadStatus.textContent = '正在上传...';
        
        // 发送到服务器
        fetch('/upload_voice_sample', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('上传失败');
            }
            return response.json();
        })
        .then(data => {
            // 上传成功
            uploadStatus.textContent = '上传成功！正在处理语音样本...';
            uploadStatus.style.color = '#ffc107'; // 黄色，表示处理中
            
            // 保存speaker_id到localStorage
            currentSpeakerId = data.speaker_id;
            localStorage.setItem('voiceSampleSpeakerId', data.speaker_id);
            
            // 开始轮询状态
            startStatusPolling(data.speaker_id);
        })
        .catch(error => {
            console.error('上传错误:', error);
            uploadStatus.textContent = '上传失败，请重试';
            uploadStatus.style.color = '#dc3545';
        });
    }
    
    // 开始轮询语音克隆状态
    function startStatusPolling(speakerId) {
        // 清除之前的轮询
        if (statusCheckInterval) {
            clearInterval(statusCheckInterval);
        }
        
        // 设置轮询间隔（每2秒检查一次）
        statusCheckInterval = setInterval(() => {
            checkCloneStatus(speakerId);
        }, 2000);
    }
    
    // 检查语音克隆状态
    function checkCloneStatus(speakerId) {
        fetch(`/clone_status?speaker_id=${speakerId}`)
        .then(response => response.json())
        .then(data => {
            if (data.status === 'ready') {
                // 处理完成
                uploadStatus.textContent = '语音克隆已准备就绪！你可以开始实时翻译了！';
                uploadStatus.style.color = '#198754'; // 绿色，表示成功
                
                // 清除轮询
                if (statusCheckInterval) {
                    clearInterval(statusCheckInterval);
                    statusCheckInterval = null;
                }
                
                // 显示成功提示
                setTimeout(() => {
                    alert('语音克隆已准备就绪！你可以开始实时翻译了！');
                }, 500);
            } else if (data.status === 'pending') {
                // 仍在处理中
                uploadStatus.textContent = '正在处理语音样本...';
                uploadStatus.style.color = '#ffc107'; // 黄色，表示处理中
            } else {
                // 处理失败
                uploadStatus.textContent = `处理失败: ${data.message || '未知错误'}`;
                uploadStatus.style.color = '#dc3545'; // 红色，表示失败
                
                // 清除轮询
                if (statusCheckInterval) {
                    clearInterval(statusCheckInterval);
                    statusCheckInterval = null;
                }
            }
        })
        .catch(error => {
            console.error('检查状态错误:', error);
            uploadStatus.textContent = '检查状态失败，请刷新页面重试';
            uploadStatus.style.color = '#dc3545';
            
            // 清除轮询
            if (statusCheckInterval) {
                clearInterval(statusCheckInterval);
                statusCheckInterval = null;
            }
        });
    }
}); 