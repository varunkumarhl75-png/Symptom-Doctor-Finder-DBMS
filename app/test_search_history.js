const assert = require('node:assert/strict');
const test = require('node:test');

global.document = {
    createElement(tagName) {
        return {
            tagName,
            children: [],
            dataset: {},
            listeners: {},
            appendChild(child) {
                this.children.push(child);
            },
            addEventListener(name, callback) {
                this.listeners[name] = callback;
            },
            replaceChildren() {
                this.children = [];
            }
        };
    }
};

const renderSearchHistory = require('./static/search_history.js');

function createHistoryBox() {
    return {
        children: [],
        appendChild(child) {
            this.children.push(child);
        },
        replaceChildren() {
            this.children = [];
        }
    };
}

test('malicious stored history strings are rendered as text, not markup', () => {
    const attacks = [
        '<script>globalThis.pwned = true</script>',
        '<img src=x onerror="globalThis.pwned = true">',
        '"><svg onload="globalThis.pwned = true">'
    ];
    const historyBox = createHistoryBox();
    globalThis.pwned = false;

    renderSearchHistory(attacks, historyBox, () => {
        throw new Error('Rendering must not select or execute a history item.');
    });

    assert.equal(historyBox.children.length, attacks.length);
    assert.equal(globalThis.pwned, false);
    historyBox.children.forEach((element, index) => {
        assert.equal(element.tagName, 'button');
        assert.equal(element.textContent, attacks[index]);
        assert.equal(element.children.length, 0);
    });
    delete globalThis.pwned;
});

test('normal recent searches remain visible and selectable', () => {
    const history = ['chest pain', 'shortness of breath'];
    const historyBox = createHistoryBox();
    const selected = [];

    renderSearchHistory(history, historyBox, query => selected.push(query));

    assert.deepEqual(
        historyBox.children.map(element => element.textContent),
        history
    );
    historyBox.children[1].listeners.click();
    assert.deepEqual(selected, ['shortness of breath']);
});

test('empty history displays the existing empty-state message', () => {
    const historyBox = createHistoryBox();

    renderSearchHistory([], historyBox, () => {});

    assert.equal(historyBox.children.length, 1);
    assert.equal(historyBox.children[0].className, 'empty-history');
    assert.equal(
        historyBox.children[0].textContent,
        'Your recent searches will appear here.'
    );
});
