function renderSearchHistory(history, historyBox, onSelect) {
    historyBox.replaceChildren();

    if (!history.length) {
        const emptyMessage = document.createElement('span');
        emptyMessage.className = 'empty-history';
        emptyMessage.textContent = 'Your recent searches will appear here.';
        historyBox.appendChild(emptyMessage);
        return;
    }

    history.forEach(query => {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'history-item';
        item.dataset.query = query;
        item.textContent = query;
        item.addEventListener('click', () => onSelect(item.dataset.query));
        historyBox.appendChild(item);
    });
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = renderSearchHistory;
}
