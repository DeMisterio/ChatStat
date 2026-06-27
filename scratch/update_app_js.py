import os

with open("frontend/app.js", "r", encoding="utf-8") as f:
    content = f.read()

handle_file_logic = """let currentFileForUpload = null;

async function handleFile(file, forceAction = null) {
    if (!file.name.endsWith('.json') && !file.name.endsWith('.txt') && !file.name.endsWith('.zip')) {
        alert("Пожалуйста, загрузите файл с расширением .json, .txt или .zip");
        return;
    }
    currentFileForUpload = file;

    showView('progress');
    const formData = new FormData();
    formData.append('file', file);
    formData.append('use_llm', useLlmToggle.checked);
    formData.append('llm_model', llmModelSelect.value || 'qwen2.5:1.5b');
    if (forceAction) {
        formData.append('force_action', forceAction);
    }

    try {
        const res = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        if (!res.ok) {
            throw new Error((await res.json()).error || "Ошибка загрузки");
        }
        
        const data = await res.json();
        
        if (data.status === "needs_decision") {
            // Show modal
            document.getElementById('checkpoint-modal').style.display = 'block';
            let dateStr = new Date(data.last_updated).toLocaleString();
            document.getElementById('checkpoint-date-text').innerText = "Дата последнего анализа: " + dateStr;
            window.currentFileHash = data.file_hash;
            return;
        }
        
        document.getElementById('checkpoint-modal').style.display = 'none';
        
        const sf = document.getElementById('source-format');
        if (data.source) {
            sf.style.display = 'block';
            sf.innerText = `Обнаружен формат: ${data.source === 'whatsapp' ? 'WhatsApp' : 'Telegram'}`;
        } else {
            sf.style.display = 'none';
        }
        connectWebSocket(data.task_id);
    } catch (err) {
        showError("Ошибка отправки файла", err.message);
    }
}

// Modal event listeners
document.getElementById('btn-load-checkpoint').addEventListener('click', () => {
    document.getElementById('checkpoint-modal').style.display = 'none';
    if (currentFileForUpload) {
        handleFile(currentFileForUpload, "load");
    }
});

document.getElementById('btn-recalc-checkpoint').addEventListener('click', () => {
    document.getElementById('checkpoint-modal').style.display = 'none';
    if (currentFileForUpload) {
        handleFile(currentFileForUpload, "recalculate");
    }
});

document.getElementById('delete-checkpoint-btn').addEventListener('click', async () => {
    if (!window.currentFileHash) return;
    if (confirm("Вы уверены, что хотите удалить сохранённые данные анализа?")) {
        try {
            await fetch(`/api/checkpoints/${window.currentFileHash}`, { method: 'DELETE' });
            alert("Данные успешно удалены.");
            location.reload();
        } catch (err) {
            alert("Ошибка удаления");
        }
    }
});
"""

# Replace the old handleFile function with the new logic
start_idx = content.find("async function handleFile(file) {")
if start_idx != -1:
    end_idx = content.find("function showError(", start_idx)
    content = content[:start_idx] + handle_file_logic + "\n" + content[end_idx:]

with open("frontend/app.js", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated app.js")
