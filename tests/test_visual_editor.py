import os
import sys
# Windows offscreen does not resolve bold font variants reliably. Use the
# native Windows Qt plugin on its hosted runner; other platforms use offscreen.
if sys.platform != 'win32':
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QTextCursor
from markdown_pretty_viewer.visual_editor import VisualEditor, semantic_signature
from markdown_pretty_viewer.file_scanner import read_markdown_file, write_markdown_file

@pytest.fixture(scope='session')
def app():
    return QApplication.instance() or QApplication([])

@pytest.fixture
def editor(app):
    widget = VisualEditor()
    yield widget
    widget.close()

DOCUMENT = '''---
title: Preserved
---

# Instructions

Change **this text** only.

- First
- Second

| Name | Value |
| --- | --- |
| Test | 42 |

```mermaid
graph TD
A-->B
```

```python
print("keep precisely")
```

Formula $x^2$.

<div>custom HTML</div>

![Image](private.png)

[Reference][doc]

[doc]: https://example.com "Title"
'''

@pytest.mark.parametrize('source', [DOCUMENT, '', '\n\n', 'Simple', '\ufeff' + DOCUMENT,
                                       DOCUMENT.replace('\n', '\r\n')])
def test_no_edit_is_identical(editor, source):
    editor.load_markdown(source)
    assert editor.markdown() == source
    assert not editor.is_modified()


def test_edit_preserves_all_other_source(editor):
    editor.load_markdown(DOCUMENT)
    card = next(c for c in editor.cards if c.source.startswith('Change'))
    assert not card.protected, (card.source, card.baseline)
    cursor = card.text.textCursor()
    cursor.movePosition(QTextCursor.End)
    cursor.insertText(' Added.')
    output = editor.markdown()
    assert editor.is_modified()
    for other in editor.cards:
        if other is not card:
            assert other.source in output
    assert 'Added.' in output


def test_format_and_undo(editor):
    editor.load_markdown('Normal text.\n')
    card = editor.cards[0]
    editor.activate(card)
    cursor = card.text.textCursor()
    cursor.select(QTextCursor.Document)
    card.text.setTextCursor(cursor)
    editor.format('bold')
    assert '**Normal text.**' in editor.markdown()
    editor.undo()
    assert editor.markdown() == 'Normal text.\n'
    editor.heading(2)
    assert editor.markdown().startswith('## ')


def test_tables_and_lists_are_visual_and_editable(editor):
    editor.load_markdown('- One\n- Two\n\n| A | B |\n|---|---|\n| C | D |\n')
    assert not any(c.protected for c in editor.cards)
    table = editor.cards[-1]
    cursor = table.text.textCursor()
    cursor.movePosition(QTextCursor.Start)
    while cursor.currentTable() is None and not cursor.atEnd():
        cursor.movePosition(QTextCursor.NextCharacter)
    cursor.currentTable().cellAt(1, 0).firstCursorPosition().insertText('New ')
    assert '|New C|D|' in editor.markdown()
    assert semantic_signature(editor.markdown())


def test_sensitive_blocks_cannot_be_formatted_or_deleted(editor):
    editor.load_markdown(DOCUMENT)
    for card in list(editor.cards):
        if card.protected:
            editor.activate(card)
            editor.format('bold')
            editor.delete_block()
            assert card in editor.cards
    assert editor.markdown() == DOCUMENT


def test_insert_move_and_delete(editor):
    editor.load_markdown('# First\n\nLast paragraph.\n')
    editor.activate(editor.cards[-1])
    editor.move_block(-1)
    assert editor.markdown().startswith('Last paragraph.\n\n# First')
    editor.add_paragraph()
    editor.active.text.insertPlainText('New paragraph')
    assert 'New paragraph' in editor.markdown()
    editor.delete_block()
    assert 'New paragraph' not in editor.markdown()


def test_save_preserves_bom_newlines_and_mode(tmp_path):
    path = tmp_path / 'test.md'
    path.write_bytes(b'\xef\xbb\xbf# Title\r\n')
    path.chmod(0o640)
    original_mode = path.stat().st_mode & 0o777
    original = read_markdown_file(path)
    write_markdown_file(path, original + 'Text\r\n')
    assert path.read_bytes() == b'\xef\xbb\xbf# Title\r\nText\r\n'
    assert path.stat().st_mode & 0o777 == original_mode


def test_failed_save_keeps_original(tmp_path, monkeypatch):
    path = tmp_path / 'test.md'
    path.write_text('Original')
    def fail(*args):
        raise OSError('disk error')
    monkeypatch.setattr(os, 'replace', fail)
    with pytest.raises(OSError):
        write_markdown_file(path, 'Changed')
    assert path.read_text() == 'Original'
    assert list(tmp_path.iterdir()) == [path]


def test_quote_and_link(editor, monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    editor.load_markdown('Some text.\n')
    card = editor.cards[0]
    editor.activate(card)
    editor.quote()
    assert editor.markdown().startswith('> ')
    cursor = card.text.textCursor()
    cursor.select(QTextCursor.Document)
    card.text.setTextCursor(cursor)
    monkeypatch.setattr(QInputDialog, 'getText', lambda *args: ('https://example.com', True))
    editor.link()
    assert '[Some text.](https://example.com)' in editor.markdown()


def test_new_table(editor, monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    editor.load_markdown('Hello\n')
    monkeypatch.setattr(QInputDialog, 'getInt', lambda *args: (2, True))
    editor.add_table()
    assert not editor.active.protected
    assert 'Columna 1' in editor.markdown()
    assert len([t for t in __import__('markdown_pretty_viewer.visual_editor', fromlist=['PARSER']).PARSER.parse(editor.markdown()) if t.type == 'table_open']) == 1


@pytest.mark.parametrize('source', ['- Item\n\n  ```python\n  print(1)\n  ```\n',
                                    'A [shortcut].\n\n[shortcut]: https://example.com\n',
                                    '::: warning\nKeep me\n:::'])
def test_extension_and_nested_code_are_protected(editor, source):
    editor.load_markdown(source)
    assert all(c.protected for c in editor.cards)
    assert editor.markdown() == source


def test_wrapped_prose_is_same_structure():
    assert semantic_signature('A sufficiently long **paragraph** with text.\n') == semantic_signature('A sufficiently long **paragraph**\nwith text.\n')
    assert semantic_signature('A  \nB\n') != semantic_signature('A\nB\n')
    assert semantic_signature('A **word**.\n') != semantic_signature('A word.\n')


def test_metadata_name_can_be_edited_visually_with_line_breaks(editor):
    source = ('**Proyecto:** Ejemplo  \n**Plataforma:** Televisión  \n'
              '**Fecha:** octubre\n\n'
              '**Versión:** un documento con una descripción suficientemente larga para que Qt la divida en varias líneas al guardarlo  \n'
              '**Nombre:** todavía no decidido. *Primer nombre*, *Segundo nombre* y *Tercer nombre* son opciones provisionales.\n\n')
    editor.load_markdown(source)
    assert all(not card.protected for card in editor.cards)
    assert editor.markdown() == source
    card = editor.cards[-1]
    cursor = card.text.document().find('todavía no decidido')
    assert not cursor.isNull()
    cursor.insertText('Nombre definitivo')
    output = editor.markdown()
    assert 'Nombre definitivo' in output
    assert semantic_signature(output) == semantic_signature(source.replace('todavía no decidido', 'Nombre definitivo'))
    assert editor.cards[0].source in output


def test_hard_break_after_emoji(editor):
    source = 'Texto 😀  \n**Nombre:** con *cursiva*.\n'
    editor.load_markdown(source)
    assert not editor.cards[0].protected
    cursor = editor.cards[0].text.document().find('Nombre')
    cursor.insertText('Título')
    assert semantic_signature(editor.markdown()) == semantic_signature(source.replace('Nombre', 'Título'))
