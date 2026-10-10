"""Native, offline block editor. Unchanged/unsupported source is never serialized."""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from markdown_it import MarkdownIt
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QFontDatabase, QTextCharFormat, QTextCursor, QTextDocument, QTextListFormat, QTextFormat, QTextDocumentFragment
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
                              QTextEdit, QPushButton, QComboBox, QLabel, QInputDialog)

PARSER = MarkdownIt('commonmark').enable('table').enable('strikethrough')
FEATURES = QTextDocument.MarkdownDialectGitHub | QTextDocument.MarkdownNoHTML


def semantic_signature(source: str):
    """Compare parser structure, formatting and content, ignoring source spelling."""
    def signature(tokens):
        result = []
        for t in tokens:
            # Qt wraps long prose at a different column. CommonMark soft breaks
            # are spaces; empty text tokens are parser artifacts, not content.
            if t.type in {'text', 'softbreak'}:
                content = ' ' if t.type == 'softbreak' else re.sub(r'\s+', ' ', t.content)
                if not content:
                    continue
                if result and result[-1][0] == 'text':
                    previous = result[-1]
                    result[-1] = ('text', '', 0, re.sub(r'\s+', ' ', previous[3] + content), [], [])
                else:
                    result.append(('text', '', 0, content, [], []))
            else:
                result.append((t.type, t.tag, t.nesting, t.content if not t.children else '',
                               sorted((t.attrs or {}).items()), signature(t.children or [])))
        return result
    return signature(PARSER.parse(source))


def load_visual_markdown(document, source):
    """Keep explicit Markdown line breaks as Qt line separators, not paragraphs."""
    marker = 'MPVLINEBREAK' + uuid.uuid4().hex
    if any(child.type == 'hardbreak' for token in PARSER.parse(source) for child in (token.children or [])):
        prepared = re.sub(r'(?: {2,}|\\)\r?\n', ' ' + marker + ' ', source)
        document.setMarkdown(prepared, FEATURES)
        while True:
            cursor = document.find(' ' + marker + ' ')
            if cursor.isNull():
                break
            cursor.insertText('\u2028')
    else:
        document.setMarkdown(source, FEATURES)


def visual_markdown(document):
    """Qt's writer drops hard breaks. Preserve them explicitly during serialization."""
    if '\u2028' not in document.toRawText():
        return document.toMarkdown(FEATURES)
    # Serializing each visual line independently avoids Qt wrapping inside an
    # emphasis delimiter immediately after a hard break in the same paragraph.
    if document.blockCount() == 1 and document.firstBlock().textList() is None:
        parts = []
        start = 0
        for line in document.toRawText().split('\u2028'):
            cursor = QTextCursor(document)
            cursor.setPosition(start)
            cursor.setPosition(start + len(line.encode('utf-16-le')) // 2, QTextCursor.KeepAnchor)
            part = QTextDocument()
            part.setDefaultFont(document.defaultFont())
            QTextCursor(part).insertFragment(QTextDocumentFragment(cursor))
            parts.append(part.toMarkdown(FEATURES).strip('\n'))
            start = cursor.selectionEnd() + 1
        return '  \n'.join(parts) + '\n\n'
    marker = next(chr(c) for c in range(0xe000, 0xf8ff) if chr(c) not in document.toRawText())
    copy = document.clone()
    while True:
        cursor = copy.find('\u2028')
        if cursor.isNull():
            break
        cursor.insertText(marker)
    return copy.toMarkdown(FEATURES).replace(marker, '  \n')



@dataclass
class SourceBlock:
    source: str
    protected: bool


def source_blocks(source: str) -> list[SourceBlock]:
    lines = source.splitlines(keepends=True)
    tokens = PARSER.parse(source)
    ranges = [(t.map[0], t.map[1], t.type) for t in tokens if t.level == 0 and t.map]
    result = []
    position = 0
    for start, end, kind in ranges:
        if start < position:
            continue
        if start > position:
            gap = ''.join(lines[position:start])
            if result:
                result[-1].source += gap
            else:
                result.append(SourceBlock(gap, True))
        raw = ''.join(lines[start:end])
        protected = kind not in {'paragraph_open', 'heading_open', 'bullet_list_open',
                                 'ordered_list_open', 'table_open', 'blockquote_open'}
        # Extensions, images and reference syntax cannot safely be round-tripped by Qt.
        protected |= any(t.type in {'fence', 'code_block', 'html_block', 'html_inline', 'image'}
                         and t.map and start <= t.map[0] < end for t in tokens)
        protected |= bool(re.search(r'!\[|\$|<[^>]+>|\[\^|\]\[|^\s*\[[^\]]+\]:|\{[:.]|^\s*[-+*]\s+\[[ xX]\]|^\s*:::|\\\(|\\\[', raw, re.M))
        result.append(SourceBlock(raw, protected))
        position = end
    if position < len(lines):
        tail = ''.join(lines[position:])
        if result:
            result[-1].source += tail
        else:
            result.append(SourceBlock(tail, True))
    if re.search(r'^ {0,3}\[[^\]]+\]:', source, re.M):
        for block in result:
            if '[' in block.source:
                block.protected = True
    # YAML front matter may otherwise appear as a rule and heading: protect all of it.
    if lines and lines[0].strip() == '---':
        end = next((i + 1 for i in range(1, len(lines)) if lines[i].strip() in {'---', '...'}), 0)
        if end:
            prefix = ''.join(lines[:end])
            return [SourceBlock(prefix, True)] + source_blocks(''.join(lines[end:]))
    return result


class BlockTextEdit(QTextEdit):
    activated = Signal()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.activated.emit()

    def insertFromMimeData(self, source):
        # Pasted HTML can carry unsupported formatting, resources or remote images.
        self.insertPlainText(source.text())

    def loadResource(self, resource_type, name):
        # Editing must never download images or read arbitrary local resources.
        return None


class BlockCard(QWidget):
    def __init__(self, block: SourceBlock, owner):
        super().__init__()
        self.source = block.source
        self.owner = owner
        self.protected = block.protected
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        self.text = BlockTextEdit()
        self.text.setAcceptRichText(False)
        font = QFontDatabase.systemFont(QFontDatabase.GeneralFont)
        font.setPointSize(12)
        self.text.setFont(font)
        load_visual_markdown(self.text.document(), self.source)
        self.baseline = visual_markdown(self.text.document())
        if not self.protected:
            self.protected = semantic_signature(self.source) != semantic_signature(self.baseline)
        self.text.setReadOnly(self.protected)
        self.text.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text.activated.connect(lambda: owner.activate(self))
        if self.protected:
            if self.source.strip():
                layout.addWidget(QLabel('Bloque protegido · se conserva íntegro al guardar'))
            else:
                self.hide()
        layout.addWidget(self.text)
        self.text.document().setModified(False)
        self.text.textChanged.connect(owner.changed)
        self.text.document().documentLayout().documentSizeChanged.connect(self.resize_text)
        self.resize_text()

    def resize_text(self, *_):
        self.text.setMinimumHeight(max(65, int(self.text.document().size().height()) + 24))
        self.text.setMaximumHeight(self.text.minimumHeight())

    def markdown(self):
        if not self.text.document().isModified():
            return self.source
        current = visual_markdown(self.text.document())
        if self.protected or current == self.baseline:
            return self.source
        return current.rstrip() + '\n\n'


class VisualEditor(QWidget):
    modificationChanged = Signal(bool)

    def __init__(self):
        super().__init__()
        self.cards = []
        self.active = None
        self.loading = False
        self.original = ''
        self.bom = ''
        self.newline = '\n'
        self.reordered = False
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.style = QComboBox()
        self.style.addItems(['Párrafo'] + [f'Título {i}' for i in range(1, 7)])
        self.style.activated.connect(self.heading)
        toolbar.addWidget(self.style)
        for label, action in [('Negrita', lambda: self.format('bold')),
                              ('Cursiva', lambda: self.format('italic')),
                              ('Tachado', lambda: self.format('strike')),
                              ('• Lista', lambda: self.make_list(False)),
                              ('1. Lista', lambda: self.make_list(True)),
                              ('Cita', self.quote), ('Enlace', self.link), ('Deshacer', self.undo), ('Rehacer', self.redo)]:
            button = QPushButton(label)
            button.setFocusPolicy(Qt.NoFocus)
            button.clicked.connect(action)
            toolbar.addWidget(button)
        layout.addLayout(toolbar)
        blocks = QHBoxLayout()
        for label, action in [('Añadir párrafo', self.add_paragraph), ('Eliminar bloque', self.delete_block),
                              ('Subir bloque', lambda: self.move_block(-1)),
                              ('Bajar bloque', lambda: self.move_block(1)), ('Añadir tabla', self.add_table)]:
            button = QPushButton(label)
            button.setFocusPolicy(Qt.NoFocus)
            button.clicked.connect(action)
            blocks.addWidget(button)
        blocks.addStretch()
        layout.addLayout(blocks)
        layout.addWidget(QLabel('Haz clic en el texto para editarlo. Los bloques protegidos se conservan sin cambios.'))
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.addStretch()
        self.scroll.setWidget(self.body)
        self.scroll.setStyleSheet('QScrollArea { background: #f4f5f7; border: 0; }')
        self.body.setStyleSheet('QTextEdit { background: white; color: #20242b; padding: 8px; border: 1px solid #d7dbe2; border-radius: 5px; } QTextEdit:focus { border: 1px solid #5688c9; }')
        layout.addWidget(self.scroll)

    def load_markdown(self, source: str):
        self.loading = True
        for card in self.cards:
            self.body_layout.removeWidget(card)
            card.deleteLater()
        self.cards = []
        self.active = None
        self.original = source
        self.reordered = False
        self.bom = '\ufeff' if source.startswith('\ufeff') else ''
        self.newline = '\r\n' if '\r\n' in source else '\n'
        for block in source_blocks(source[len(self.bom):]):
            card = BlockCard(block, self)
            self.cards.append(card)
            self.body_layout.insertWidget(len(self.cards) - 1, card)
        self.loading = False
        self.modificationChanged.emit(False)

    def markdown(self):
        parts = []
        for card in self.cards:
            part = card.markdown()
            if part != card.source and self.newline == '\r\n':
                part = part.replace('\n', '\r\n')
            if self.reordered and parts and not parts[-1].endswith(self.newline * 2):
                parts[-1] += self.newline * (2 if not parts[-1].endswith(self.newline) else 1)
            parts.append(part)
        return self.bom + ''.join(parts)

    def is_modified(self):
        return self.markdown() != self.original

    def changed(self):
        if not self.loading:
            self.modificationChanged.emit(self.is_modified())

    def activate(self, card):
        self.active = card
        self.style.setCurrentIndex(card.text.textCursor().blockFormat().headingLevel())

    def editable(self):
        return self.active is not None and not self.active.protected

    def heading(self, level):
        if not self.editable():
            return
        cursor = self.active.text.textCursor()
        cursor.beginEditBlock()
        fmt = cursor.blockFormat()
        fmt.setHeadingLevel(level)
        cursor.mergeBlockFormat(fmt)
        char = QTextCharFormat()
        char.setFontPointSize([12, 26, 22, 19, 17, 15, 13][level])
        char.setFontWeight(QFont.Bold if level else QFont.Normal)
        cursor.select(QTextCursor.BlockUnderCursor)
        cursor.mergeCharFormat(char)
        cursor.endEditBlock()
        self.active.text.setFocus()

    def format(self, kind):
        if not self.editable():
            return
        editor = self.active.text
        current = editor.currentCharFormat()
        fmt = QTextCharFormat()
        if kind == 'bold':
            fmt.setFontWeight(QFont.Normal if current.fontWeight() >= QFont.Bold else QFont.Bold)
        elif kind == 'italic':
            fmt.setFontItalic(not current.fontItalic())
        else:
            fmt.setFontStrikeOut(not current.fontStrikeOut())
        editor.mergeCurrentCharFormat(fmt)
        editor.setFocus()

    def make_list(self, numbered):
        if self.editable():
            fmt = QTextListFormat()
            fmt.setStyle(QTextListFormat.ListDecimal if numbered else QTextListFormat.ListDisc)
            self.active.text.textCursor().createList(fmt)
            self.active.text.setFocus()

    def quote(self):
        if self.editable():
            cursor = self.active.text.textCursor()
            fmt = cursor.blockFormat()
            fmt.setProperty(QTextFormat.BlockQuoteLevel, 0 if fmt.property(QTextFormat.BlockQuoteLevel) else 1)
            cursor.mergeBlockFormat(fmt)
            self.active.text.setFocus()

    def add_table(self):
        rows, ok = QInputDialog.getInt(self, 'Añadir tabla', 'Filas de datos:', 2, 1, 50)
        if not ok:
            return
        columns, ok = QInputDialog.getInt(self, 'Añadir tabla', 'Columnas:', 2, 1, 12)
        if not ok:
            return
        source = '| ' + ' | '.join(f'Columna {i + 1}' for i in range(columns)) + ' |\n'
        source += '| ' + ' | '.join('---' for _ in range(columns)) + ' |\n'
        source += ('| ' + ' | '.join('Texto' for _ in range(columns)) + ' |\n') * rows
        card = BlockCard(SourceBlock(source + '\n', False), self)
        index = self.cards.index(self.active) + 1 if self.active else len(self.cards)
        self.cards.insert(index, card)
        self.body_layout.insertWidget(index, card)
        self.reordered = True
        self.activate(card)
        card.text.setFocus()
        self.changed()

    def link(self):
        if not self.editable():
            return
        cursor = self.active.text.textCursor()
        url, ok = QInputDialog.getText(self, 'Enlace', 'Dirección del enlace:')
        if ok and url.strip():
            fmt = QTextCharFormat()
            fmt.setAnchor(True)
            fmt.setAnchorHref(url.strip())
            fmt.setFontUnderline(True)
            if cursor.hasSelection():
                cursor.mergeCharFormat(fmt)
            else:
                cursor.insertText(url.strip(), fmt)
            self.active.text.setFocus()

    def undo(self):
        if self.editable():
            self.active.text.undo()

    def redo(self):
        if self.editable():
            self.active.text.redo()

    def add_paragraph(self):
        index = self.cards.index(self.active) + 1 if self.active else len(self.cards)
        card = BlockCard(SourceBlock('\n', False), self)
        self.reordered = True
        self.cards.insert(index, card)
        self.body_layout.insertWidget(index, card)
        card.text.setFocus()
        self.activate(card)
        self.changed()

    def delete_block(self):
        if self.editable():
            card = self.active
            self.cards.remove(card)
            self.body_layout.removeWidget(card)
            card.deleteLater()
            self.active = None
            self.changed()

    def move_block(self, delta):
        if not self.editable():
            return
        index = self.cards.index(self.active)
        target = index + delta
        if 0 <= target < len(self.cards):
            self.reordered = True
            self.cards[index], self.cards[target] = self.cards[target], self.cards[index]
            for i, card in enumerate(self.cards):
                self.body_layout.removeWidget(card)
                self.body_layout.insertWidget(i, card)
            self.changed()
