/**
 * 实时语音翻译客户端JavaScript
 * 负责解析连接信息、连接LiveKit服务器、选择语言和播放音频
 */

// 全局变量
let connectionInfo = null;      // 连接信息
let livekit = null;             // LiveKit客户端实例
let currentRoom = null;         // 当前连接的房间
let selectedLanguage = null;    // 当前选择的语言
let audioPlayer = null;         // 音频播放器
let volumeLevel = 0.7;          // 音量级别

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    // 初始化音量控制
    const volumeControl = document.getElementById('volume-control');
    volumeControl.addEventListener('input', (e) => {
        volumeLevel = parseFloat(e.target.value);
        if (audioPlayer) {
            audioPlayer.volume = volumeLevel;
        }
    });

    // 初始化重连按钮
    const reconnectButton = document.getElementById('reconnect-button');
    reconnectButton.addEventListener('click', () => {
        if (selectedLanguage) {
            connectToLanguageChannel(selectedLanguage);
        } else {
            parseConnectionInfo();
        }
    });

    // 解析URL中的连接信息
    parseConnectionInfo();
});

/**
 * 解析URL中的连接信息
 */
function parseConnectionInfo() {
    updateStatus('connecting', '正在加载连接信息...');
    
    // 从URL获取info参数
    const urlParams = new URLSearchParams(window.location.search);
    const infoParam = urlParams.get('info');
    
    if (!infoParam) {
        updateStatus('disconnected', '错误: URL中没有找到连接信息');
        showReconnectButton();
        return;
    }
    
    try {
        // 解码Base64连接信息
        const decodedInfo = atob(infoParam);
        connectionInfo = JSON.parse(decodedInfo);
        
        // 初始化LiveKit
        initializeLiveKit();
        
        // 显示可用语言
        displayLanguages();
        
        updateStatus('disconnected', '请选择一种语言以开始收听');
    } catch (error) {
        console.error('解析连接信息出错:', error);
        updateStatus('disconnected', '解析连接信息出错: ' + error.message);
        showReconnectButton();
    }
}

/**
 * 初始化LiveKit客户端
 */
function initializeLiveKit() {
    try {
        // 获取LiveKit客户端
        livekit = LivekitClient;
        console.log('LiveKit客户端已初始化');
    } catch (error) {
        console.error('LiveKit初始化失败:', error);
        updateStatus('disconnected', 'LiveKit初始化失败: ' + error.message);
        showReconnectButton();
    }
}

/**
 * 显示可用的语言选项
 */
function displayLanguages() {
    if (!connectionInfo || !connectionInfo.languages) {
        updateStatus('disconnected', '没有可用的语言信息');
        return;
    }
    
    const languageList = document.getElementById('language-list');
    languageList.innerHTML = '';
    
    // 添加中文选项
    if (connectionInfo.languages.zh) {
        addLanguageOption('zh', '中文（原声）');
    }
    
    // 添加其他语言选项
    Object.entries(connectionInfo.languages).forEach(([langCode, langInfo]) => {
        if (langCode !== 'zh') {
            addLanguageOption(langCode, langInfo.name);
        }
    });
}

/**
 * 添加语言选项到列表
 */
function addLanguageOption(langCode, langName) {
    const languageList = document.getElementById('language-list');
    
    const languageCard = document.createElement('div');
    languageCard.className = 'col-6';
    languageCard.innerHTML = `
        <div class="card language-card" data-lang="${langCode}">
            <div class="card-body text-center">
                <h5 class="card-title">${langName}</h5>
            </div>
        </div>
    `;
    
    // 添加点击事件
    const card = languageCard.querySelector('.language-card');
    card.addEventListener('click', () => {
        selectLanguage(langCode);
    });
    
    languageList.appendChild(languageCard);
}

/**
 * 选择语言并连接到对应频道
 */
function selectLanguage(langCode) {
    // 更新UI
    const languageCards = document.querySelectorAll('.language-card');
    languageCards.forEach(card => {
        if (card.dataset.lang === langCode) {
            card.classList.add('selected');
        } else {
            card.classList.remove('selected');
        }
    });
    
    // 如果选择了新语言，断开当前连接并连接到新频道
    if (selectedLanguage !== langCode) {
        // 断开当前连接
        if (currentRoom) {
            currentRoom.disconnect();
            currentRoom = null;
        }
        
        selectedLanguage = langCode;
        
        // 连接到新频道
        connectToLanguageChannel(langCode);
    }
}

/**
 * 连接到特定语言的LiveKit频道
 */
async function connectToLanguageChannel(langCode) {
    if (!connectionInfo || !connectionInfo.languages || !connectionInfo.languages[langCode]) {
        updateStatus('disconnected', `找不到${langCode}语言的连接信息`);
        return;
    }
    
    const langInfo = connectionInfo.languages[langCode];
    updateStatus('connecting', `正在连接到${langInfo.name}频道...`);
    
    try {
        // 断开现有连接
        if (currentRoom) {
            await currentRoom.disconnect();
            currentRoom = null;
        }
        
        // 创建新的房间
        currentRoom = new livekit.Room();
        
        // 设置事件监听器
        setupRoomEventListeners(currentRoom, langInfo.name);
        
        // 连接到LiveKit
        await currentRoom.connect(connectionInfo.server, langInfo.token);
        console.log(`已连接到${langInfo.name}频道`);
        
        // 自动订阅音频
        currentRoom.setAutoSubscribe(true);
        
    } catch (error) {
        console.error(`连接到${langInfo.name}频道失败:`, error);
        updateStatus('disconnected', `连接到${langInfo.name}频道失败: ${error.message}`);
        showReconnectButton();
    }
}

/**
 * 设置房间事件监听器
 */
function setupRoomEventListeners(room, languageName) {
    // 连接状态变化
    room.on(livekit.RoomEvent.ConnectionStateChanged, (state) => {
        console.log('连接状态变化:', state);
        
        if (state === livekit.ConnectionState.Connected) {
            updateStatus('connected', `已连接到${languageName}频道，等待音频...`);
            hideReconnectButton();
        } else if (state === livekit.ConnectionState.Disconnected) {
            updateStatus('disconnected', `与${languageName}频道的连接已断开`);
            showReconnectButton();
        } else if (state === livekit.ConnectionState.Connecting) {
            updateStatus('connecting', `正在连接到${languageName}频道...`);
        }
    });
    
    // 远程参与者加入
    room.on(livekit.RoomEvent.ParticipantConnected, (participant) => {
        console.log('参与者加入:', participant.identity);
    });
    
    // 远程参与者离开
    room.on(livekit.RoomEvent.ParticipantDisconnected, (participant) => {
        console.log('参与者离开:', participant.identity);
    });
    
    // 音轨订阅
    room.on(livekit.RoomEvent.TrackSubscribed, (track, publication, participant) => {
        console.log('订阅了音轨:', track.kind, '来自', participant.identity);
        
        if (track.kind === livekit.Track.Kind.Audio) {
            handleAudioTrack(track);
        }
    });
    
    // 音轨取消订阅
    room.on(livekit.RoomEvent.TrackUnsubscribed, (track, publication, participant) => {
        console.log('取消订阅音轨:', track.kind, '来自', participant.identity);
    });
}

/**
 * 处理音频轨道
 */
function handleAudioTrack(track) {
    updateStatus('connected', `正在播放${selectedLanguage}音频...`);
    
    // 获取音频元素
    audioPlayer = track.mediaStreamTrack;
    
    // 设置音量
    if (audioPlayer) {
        audioPlayer.volume = volumeLevel;
    }
}

/**
 * 更新连接状态UI
 */
function updateStatus(state, message) {
    const statusDot = document.getElementById('status-dot');
    const connectionStatus = document.getElementById('connection-status');
    const statusMessage = document.getElementById('status-message');
    
    // 更新状态指示点
    statusDot.className = 'status-indicator';
    if (state === 'connected') {
        statusDot.classList.add('status-connected');
        connectionStatus.textContent = '已连接';
    } else if (state === 'connecting') {
        statusDot.classList.add('status-connecting');
        connectionStatus.textContent = '连接中';
    } else {
        statusDot.classList.add('status-disconnected');
        connectionStatus.textContent = '未连接';
    }
    
    // 更新状态消息
    statusMessage.textContent = message;
}

/**
 * 显示重连按钮
 */
function showReconnectButton() {
    const reconnectContainer = document.getElementById('reconnect-container');
    reconnectContainer.classList.remove('d-none');
}

/**
 * 隐藏重连按钮
 */
function hideReconnectButton() {
    const reconnectContainer = document.getElementById('reconnect-container');
    reconnectContainer.classList.add('d-none');
} 