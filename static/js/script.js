const inputText = document.getElementById('inputText');
const outputText = document.getElementById('outputText');
const sourceLang = document.getElementById('sourceLang');
const targetLang = document.getElementById('targetLang');
const translateBtn = document.getElementById('translateBtn');
const clearBtn = document.getElementById('clearBtn');
const swapLangs = document.getElementById('swapLangs');
const historyContainer = document.getElementById('historyContainer');
const historyToggle = document.getElementById('historyToggle');
const historyList = document.getElementById('historyList');
const emptyHistory = document.getElementById('emptyHistory');
const charCount = document.getElementById('charCount');
const translatedCharCount = document.getElementById('translatedCharCount');

// Character count update
inputText.addEventListener('input', () => {
    charCount.textContent = inputText.value.length;
});

// Swap languages
swapLangs.addEventListener('click', () => {
    const tempLang = sourceLang.value;
    sourceLang.value = targetLang.value;
    targetLang.value = tempLang;
    
    if (inputText.value && outputText.value) {
        const tempText = inputText.value;
        inputText.value = outputText.value;
        outputText.value = tempText;
        
        charCount.textContent = inputText.value.length;
        translatedCharCount.textContent = outputText.value.length;
    }
});

// Clear text
clearBtn.addEventListener('click', () => {
    inputText.value = '';
    outputText.value = '';
    charCount.textContent = '0';
    translatedCharCount.textContent = '0';
    inputText.focus();
});

// Toggle history
historyToggle.addEventListener('click', () => {
    historyContainer.classList.toggle('visible');
    const icon = historyToggle.querySelector('i');
    icon.classList.toggle('fa-chevron-down');
    icon.classList.toggle('fa-chevron-up');
    
    if (historyContainer.classList.contains('visible')) {
        fetchHistory();
    }
});

// Translate function using our backend API
async function translateText() {
    const text = inputText.value.trim();
    if (!text) {
        outputText.value = 'Please enter text to translate';
        return;
    }
    
    const source = sourceLang.value;
    const target = targetLang.value;

    if (source === target) {
        outputText.value = text;
        return;
    }
    
    // Show loading state
    translateBtn.disabled = true;
    translateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Translating...';
    translateBtn.classList.add('translating');
    outputText.value = 'Translating...';
    
    try {
        // Using our backend translation endpoint
        const response = await fetch('/translate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                text: text,
                source_lang: source,
                target_lang: target
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Translation failed');
        }

        outputText.value = data.translated_text;
        translatedCharCount.textContent = data.translated_text.length;
        
        // Add to history
        addToHistory(text, data.translated_text, source === 'auto' ? 'auto' : source, target);
    } catch (error) {
        console.error('Translation error:', error);
        outputText.value = 'Error: ' + (error.message || 'Translation service unavailable. Please try again later.');
    } finally {
        // Reset button state
        translateBtn.disabled = false;
        translateBtn.innerHTML = '<i class="fas fa-exchange-alt"></i> Translate';
        translateBtn.classList.remove('translating');
    }
}

// Simple language detection (for demo purposes)
function detectLanguage(text) {
    // This is a very basic detection - in a real app you'd use a proper detection API
    const commonEnglishWords = ['the', 'be', 'to', 'of', 'and', 'a', 'in', 'that'];
    const isEnglish = commonEnglishWords.some(word => 
        text.toLowerCase().includes(word + ' ') || 
        text.toLowerCase().includes(' ' + word)
    );
    return isEnglish ? 'en' : 'es'; // Default to Spanish if not English
}

function addToHistory(original, translated, source, target) {
    const historyItem = document.createElement('li');
    historyItem.innerHTML = `
        <div class="history-item">
            <div class="history-text">
                <strong>${original}</strong>
                <i class="fas fa-arrow-right"></i>
                <strong>${translated}</strong>
                <button class="copy-btn" title="Copy translation">
                    <i class="far fa-copy"></i>
                </button>
            </div>
            <div class="history-meta">
                <span>${source.toUpperCase()} → ${target.toUpperCase()}</span>
                <span>${new Date().toLocaleString()}</span>
            </div>
        </div>
    `;
    
    historyList.prepend(historyItem);
    
    if (emptyHistory) {
        emptyHistory.style.display = 'none';
    }
    
    const copyBtn = historyItem.querySelector('.copy-btn');
    copyBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(translated);
        copyBtn.innerHTML = '<i class="fas fa-check"></i>';
        setTimeout(() => {
            copyBtn.innerHTML = '<i class="far fa-copy"></i>';
        }, 2000);
    });
}

function fetchHistory() {
    // In a real app, you would fetch this from your backend
    console.log('Fetching translation history...');
}

// Add event listeners
translateBtn.addEventListener('click', translateText);
inputText.addEventListener('keypress', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        translateText();
    }
});

// Initialize
if (historyList.children.length === 0 && emptyHistory) {
    emptyHistory.style.display = 'block';
}
