"""AST-aware structural reading via tree-sitter.

Extracts function/class signatures from source files without including
full bodies, reducing token consumption by 80-97% for large files.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LanguageConfig:
    """Tree-sitter language configuration for a file extension."""

    ts_module: str
    ts_language_fn: str = "language"
    function_types: frozenset[str] = frozenset()
    class_types: frozenset[str] = frozenset()
    import_types: frozenset[str] = frozenset()
    # Node types that represent exportable declarations
    export_patterns: frozenset[str] = frozenset()
    # Field name for the symbol's identifier
    name_field: str = "name"
    # Field name for the function/class body
    body_field: str = "body"
    # Node types for decorators/attributes
    decorator_types: frozenset[str] = frozenset()
    # Additional types to capture as top-level symbols (constants, types, etc.)
    extra_symbol_types: frozenset[str] = frozenset()
    # Node types to capture only when no functions/classes were found.
    fallback_symbol_types: frozenset[str] = frozenset()


LANGUAGES: dict[str, LanguageConfig] = {
    ".py": LanguageConfig(
        ts_module="tree_sitter_python",
        function_types=frozenset({"function_definition"}),
        class_types=frozenset({"class_definition"}),
        import_types=frozenset({"import_statement", "import_from_statement"}),
        decorator_types=frozenset({"decorator"}),
        fallback_symbol_types=frozenset({"expression_statement"}),
    ),
    ".js": LanguageConfig(
        ts_module="tree_sitter_javascript",
        function_types=frozenset({"function_declaration", "method_definition"}),
        class_types=frozenset({"class_declaration"}),
        import_types=frozenset({"import_statement"}),
        export_patterns=frozenset({"export_statement"}),
        extra_symbol_types=frozenset({"lexical_declaration"}),
    ),
    ".ts": LanguageConfig(
        ts_module="tree_sitter_typescript",
        ts_language_fn="language_typescript",
        function_types=frozenset({"function_declaration", "method_definition"}),
        class_types=frozenset({"class_declaration", "interface_declaration"}),
        import_types=frozenset({"import_statement"}),
        export_patterns=frozenset({"export_statement"}),
        extra_symbol_types=frozenset({
            "lexical_declaration", "type_alias_declaration",
        }),
    ),
    ".tsx": LanguageConfig(
        ts_module="tree_sitter_typescript",
        ts_language_fn="language_tsx",
        function_types=frozenset({"function_declaration", "method_definition"}),
        class_types=frozenset({"class_declaration", "interface_declaration"}),
        import_types=frozenset({"import_statement"}),
        export_patterns=frozenset({"export_statement"}),
        extra_symbol_types=frozenset({
            "lexical_declaration", "type_alias_declaration",
        }),
    ),
    ".jsx": LanguageConfig(
        ts_module="tree_sitter_javascript",
        function_types=frozenset({"function_declaration", "method_definition"}),
        class_types=frozenset({"class_declaration"}),
        import_types=frozenset({"import_statement"}),
        export_patterns=frozenset({"export_statement"}),
        extra_symbol_types=frozenset({"lexical_declaration"}),
    ),
    # --- Optional languages (require extras: pip install skimcode[all]) ---
    ".rs": LanguageConfig(
        ts_module="tree_sitter_rust",
        function_types=frozenset({"function_item"}),
        class_types=frozenset({"struct_item", "enum_item", "impl_item", "trait_item"}),
        import_types=frozenset({"use_declaration"}),
        name_field="name",
        body_field="body",
        extra_symbol_types=frozenset({"const_item", "static_item", "type_item"}),
    ),
    ".go": LanguageConfig(
        ts_module="tree_sitter_go",
        function_types=frozenset({"function_declaration", "method_declaration"}),
        class_types=frozenset({"type_declaration"}),
        import_types=frozenset({"import_declaration"}),
        name_field="name",
        body_field="body",
    ),
    ".java": LanguageConfig(
        ts_module="tree_sitter_java",
        function_types=frozenset({"method_declaration", "constructor_declaration"}),
        class_types=frozenset({"class_declaration", "interface_declaration", "enum_declaration"}),
        import_types=frozenset({"import_declaration"}),
        name_field="name",
        body_field="body",
        decorator_types=frozenset({"marker_annotation", "annotation"}),
    ),
    ".rb": LanguageConfig(
        ts_module="tree_sitter_ruby",
        function_types=frozenset({"method", "singleton_method"}),
        class_types=frozenset({"class", "module"}),
        import_types=frozenset(),
        name_field="name",
        body_field="body",
    ),
    ".c": LanguageConfig(
        ts_module="tree_sitter_c",
        function_types=frozenset({"function_definition"}),
        class_types=frozenset({"struct_specifier"}),
        import_types=frozenset({"preproc_include"}),
        name_field="declarator",
        body_field="body",
    ),
    ".cpp": LanguageConfig(
        ts_module="tree_sitter_cpp",
        function_types=frozenset({"function_definition"}),
        class_types=frozenset({"class_specifier", "struct_specifier"}),
        import_types=frozenset({"preproc_include"}),
        name_field="declarator",
        body_field="body",
    ),
    ".h": LanguageConfig(
        ts_module="tree_sitter_c",
        function_types=frozenset({"function_definition"}),
        class_types=frozenset({"struct_specifier"}),
        import_types=frozenset({"preproc_include"}),
        name_field="declarator",
        body_field="body",
    ),
    ".hpp": LanguageConfig(
        ts_module="tree_sitter_cpp",
        function_types=frozenset({"function_definition"}),
        class_types=frozenset({"class_specifier", "struct_specifier"}),
        import_types=frozenset({"preproc_include"}),
        name_field="declarator",
        body_field="body",
    ),
    ".swift": LanguageConfig(
        ts_module="tree_sitter_swift",
        function_types=frozenset({"function_declaration", "init_declaration"}),
        class_types=frozenset({"class_declaration", "protocol_declaration", "struct_declaration"}),
        import_types=frozenset({"import_declaration"}),
        name_field="name",
        body_field="body",
    ),
    ".kt": LanguageConfig(
        ts_module="tree_sitter_kotlin",
        function_types=frozenset({"function_declaration"}),
        class_types=frozenset({"class_declaration", "object_declaration"}),
        import_types=frozenset({"import_header"}),
        name_field="name",
        body_field="body",
        decorator_types=frozenset({"annotation"}),
    ),
}


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class SymbolInfo:
    """A single extracted symbol (function, class, type, etc.)."""

    name: str
    kind: str  # "function", "class", "method", "type", "interface", "constant"
    signature: str  # The full signature line(s) without body
    start_line: int
    end_line: int
    children: list[SymbolInfo] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    is_exported: bool = False


@dataclass
class SkimResult:
    """Result of a structural read operation."""

    content: str
    mode: str  # "full", "structural", "symbol", "head_tail"
    original_lines: int
    summary_lines: int = 0
    symbols_count: int = 0


# ---------------------------------------------------------------------------
# Parser cache (avoid re-importing on repeated calls within a process)
# ---------------------------------------------------------------------------

_parser_cache: dict[str, object] = {}


def _get_parser(config: LanguageConfig):
    """Lazily load and cache a tree-sitter parser for a language."""
    cache_key = f"{config.ts_module}:{config.ts_language_fn}"
    if cache_key in _parser_cache:
        return _parser_cache[cache_key]

    mod = importlib.import_module(config.ts_module)
    from tree_sitter import Language, Parser

    lang_fn = getattr(mod, config.ts_language_fn, None)
    if lang_fn is None:
        lang_fn = getattr(mod, "language", None)
    if lang_fn is None:
        raise ImportError(f"No language function in {config.ts_module}")

    language = Language(lang_fn())
    parser = Parser(language)
    _parser_cache[cache_key] = parser
    return parser


# ---------------------------------------------------------------------------
# Core: structural_read
# ---------------------------------------------------------------------------

def structural_read(path: Path, *, small_file_threshold: int = 150) -> SkimResult:
    """Return structural summary for large files, full content for small ones.

    For files under ``small_file_threshold`` lines, returns the full content.
    For larger files, parses with tree-sitter and returns function/class
    signatures without bodies.
    """
    content = path.read_text(encoding="utf-8", errors="replace")
    lines = content.split("\n")
    total = len(lines)

    if total <= small_file_threshold:
        return SkimResult(content=content, mode="full", original_lines=total)

    ext = path.suffix.lower()
    config = LANGUAGES.get(ext)
    if not config:
        return _head_tail_fallback(path, content, lines)

    try:
        parser = _get_parser(config)
    except ImportError:
        return _head_tail_fallback(path, content, lines)

    source = content.encode("utf-8")
    tree = parser.parse(source)

    symbols = _extract_symbols(tree.root_node, config, source, lines)
    imports = _extract_imports(tree.root_node, config, source)
    summary = _format_structural_summary(path, lines, symbols, imports)

    return SkimResult(
        content=summary,
        mode="structural",
        original_lines=total,
        summary_lines=summary.count("\n") + 1,
        symbols_count=sum(1 + len(s.children) for s in symbols),
    )


# ---------------------------------------------------------------------------
# Core: read_symbol
# ---------------------------------------------------------------------------

def read_symbol(path: Path, symbol_name: str) -> SkimResult:
    """Read a specific function/class/method by name.

    Supports dotted notation: ``Class.method`` for methods.
    """
    content = path.read_text(encoding="utf-8", errors="replace")
    lines = content.split("\n")
    ext = path.suffix.lower()
    config = LANGUAGES.get(ext)

    if not config:
        return SkimResult(
            content=f"// Unsupported file type: {ext}",
            mode="symbol",
            original_lines=len(lines),
        )

    try:
        parser = _get_parser(config)
    except ImportError:
        return SkimResult(
            content=f"// tree-sitter module not installed: {config.ts_module}",
            mode="symbol",
            original_lines=len(lines),
        )

    source = content.encode("utf-8")
    tree = parser.parse(source)
    symbols = _extract_symbols(tree.root_node, config, source, lines)

    parts = symbol_name.split(".", 1)
    target_name = parts[0]
    method_name = parts[1] if len(parts) > 1 else None

    for sym in symbols:
        if sym.name == target_name:
            if method_name:
                for child in sym.children:
                    if child.name == method_name:
                        body = "\n".join(lines[child.start_line - 1 : child.end_line])
                        return SkimResult(
                            content=body, mode="symbol",
                            original_lines=len(lines),
                            summary_lines=child.end_line - child.start_line + 1,
                        )
                return SkimResult(
                    content=f"// Symbol not found: {symbol_name}",
                    mode="symbol", original_lines=len(lines),
                )
            else:
                body = "\n".join(lines[sym.start_line - 1 : sym.end_line])
                return SkimResult(
                    content=body, mode="symbol",
                    original_lines=len(lines),
                    summary_lines=sym.end_line - sym.start_line + 1,
                )

    return SkimResult(
        content=f"// Symbol not found: {symbol_name}",
        mode="symbol", original_lines=len(lines),
    )


# ---------------------------------------------------------------------------
# Internal: symbol extraction
# ---------------------------------------------------------------------------

def _node_text(node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _extract_symbols(
    root,
    config: LanguageConfig,
    source: bytes,
    lines: list[str],
) -> list[SymbolInfo]:
    """Walk the AST and extract top-level symbols with their signatures."""
    symbols: list[SymbolInfo] = []

    for node in root.children:
        exported = False
        wrapper_decorators: list[str] = []

        actual_node = node
        if node.type in config.export_patterns:
            exported = True
            for child in node.children:
                if child.type in config.function_types | config.class_types | config.extra_symbol_types:
                    actual_node = child
                    break
            else:
                sig = _get_export_signature(node, source, lines)
                if sig:
                    symbols.append(sig)
                    symbols[-1].is_exported = True
                continue

        decorators: list[str] = []
        if node.type in config.decorator_types:
            continue

        actual_node, wrapper_decorators = _unwrap_decorated_symbol(
            actual_node,
            config,
            source,
        )
        if actual_node is None:
            continue

        decorators.extend(wrapper_decorators)

        dec_idx = _find_decorators_before(root, node, config)
        if dec_idx:
            decorators.extend(dec for dec in dec_idx if dec not in decorators)

        if actual_node.type in config.function_types:
            sym = _extract_function_symbol(actual_node, config, source, lines)
            if sym:
                sym.decorators = decorators
                sym.is_exported = exported
                symbols.append(sym)

        elif actual_node.type in config.class_types:
            sym = _extract_class_symbol(actual_node, config, source, lines)
            if sym:
                sym.decorators = decorators
                sym.is_exported = exported
                symbols.append(sym)

        elif actual_node.type in config.extra_symbol_types:
            sym = _extract_extra_symbol(actual_node, config, source, lines)
            if sym:
                sym.is_exported = exported
                symbols.append(sym)

    if symbols or not config.fallback_symbol_types:
        return symbols

    for node in root.children:
        if node.type not in config.fallback_symbol_types:
            continue

        sym = _extract_extra_symbol(node, config, source, lines)
        if sym:
            symbols.append(sym)

    return symbols


def _extract_function_symbol(
    node, config: LanguageConfig, source: bytes, lines: list[str]
) -> SymbolInfo | None:
    """Extract a function declaration's signature."""
    name_node = node.child_by_field_name(config.name_field)
    if not name_node:
        return None

    name = _node_text(name_node, source)
    sig = _get_signature_line(node, config, source, lines)

    return SymbolInfo(
        name=name,
        kind="function",
        signature=sig,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
    )


def _extract_class_symbol(
    node, config: LanguageConfig, source: bytes, lines: list[str]
) -> SymbolInfo | None:
    """Extract a class/interface with its method signatures."""
    name_node = node.child_by_field_name(config.name_field)
    if not name_node:
        return None

    name = _node_text(name_node, source)
    kind = "interface" if "interface" in node.type else "class"
    sig = _get_signature_line(node, config, source, lines)

    children: list[SymbolInfo] = []
    body = node.child_by_field_name(config.body_field)
    if body:
        for child in body.children:
            method_node, method_decorators = _unwrap_decorated_symbol(child, config, source)
            if method_node and method_node.type in config.function_types:
                method = _extract_function_symbol(method_node, config, source, lines)
                if method:
                    method.kind = "method"
                    method.decorators = method_decorators
                    children.append(method)

    return SymbolInfo(
        name=name,
        kind=kind,
        signature=sig,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        children=children,
    )


def _extract_extra_symbol(
    node, config: LanguageConfig, source: bytes, lines: list[str]
) -> SymbolInfo | None:
    """Extract type aliases, constants, etc."""
    text = _node_text(node, source)
    first_line = text.split("\n")[0].rstrip()

    assignment_node = None
    if node.type == "expression_statement":
        assignment_node = next((child for child in node.children if child.type == "assignment"), None)
        if assignment_node is None:
            return None

    name_node = node.child_by_field_name(config.name_field)
    if name_node:
        name = _node_text(name_node, source)
    elif assignment_node is not None:
        left_node = assignment_node.child_by_field_name("left")
        if left_node is None:
            return None
        name = _node_text(left_node, source)
    else:
        # Heuristic: pull name from first assignment or declaration
        for child in node.children:
            if child.type == "variable_declarator":
                n = child.child_by_field_name("name")
                if n:
                    name = _node_text(n, source)
                    break
            elif child.type == "type_alias_declaration":
                n = child.child_by_field_name("name")
                if n:
                    name = _node_text(n, source)
                    break
        else:
            name = first_line[:40]

    if node.type == "type_alias_declaration":
        kind = "type"
    elif assignment_node is not None:
        kind = "constant"
    elif "const" in first_line or "let" in first_line or "var" in first_line:
        kind = "constant"
    else:
        kind = "declaration"

    # For multi-line types/objects, collapse to signature only
    if "\n" in text and ("{" in first_line or "=" in first_line):
        sig = first_line
    else:
        sig = text.rstrip()

    return SymbolInfo(
        name=name,
        kind=kind,
        signature=sig,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
    )


def _get_signature_line(node, config: LanguageConfig, source: bytes, lines: list[str]) -> str:
    """Get the signature portion of a function/class (everything before the body)."""
    body = node.child_by_field_name(config.body_field)
    if body:
        sig_end = body.start_byte
        sig_text = source[node.start_byte:sig_end].decode("utf-8", errors="replace").rstrip()
        # Remove trailing colon / opening brace
        sig_text = sig_text.rstrip(": {").rstrip()
        if not sig_text:
            return lines[node.start_point[0]].rstrip()
        return sig_text
    return lines[node.start_point[0]].rstrip()


def _get_export_signature(node, source: bytes, lines: list[str]) -> SymbolInfo | None:
    """Handle export statements that wrap other declarations."""
    text = _node_text(node, source)
    first_line = text.split("\n")[0].rstrip()

    for child in node.children:
        name_node = child.child_by_field_name("name")
        if name_node:
            name = _node_text(name_node, source)
            if "type" in child.type:
                kind = "type"
            elif "interface" in child.type:
                kind = "interface"
            else:
                kind = "export"
            return SymbolInfo(
                name=name, kind=kind, signature=first_line,
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
            )

    if "=" in first_line or "type " in first_line:
        name = first_line.split("=")[0].replace("export", "").replace("const", "").replace("type", "").strip()
        return SymbolInfo(
            name=name, kind="export", signature=first_line,
            start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
        )
    return None


def _find_decorators_before(root, target_node, config: LanguageConfig) -> list[str]:
    """Find decorator nodes immediately preceding a function/class."""
    if not config.decorator_types:
        return []

    decorators: list[str] = []
    prev = None
    for child in root.children:
        if child is target_node and prev and prev.type in config.decorator_types:
            # Collect consecutive decorators going backwards
            idx = list(root.children).index(target_node)
            for i in range(idx - 1, -1, -1):
                c = root.children[i]
                if c.type in config.decorator_types:
                    decorators.insert(0, c.text.decode("utf-8", errors="replace").strip())
                else:
                    break
        prev = child
    return decorators


def _unwrap_decorated_symbol(node, config: LanguageConfig, source: bytes):
    """Unwrap tree-sitter decorated_definition nodes to their real symbol."""
    decorators: list[str] = []
    current = node

    while current is not None and current.type == "decorated_definition":
        inner = None
        for child in current.children:
            if child.type in config.decorator_types:
                decorators.append(_node_text(child, source).strip())
            elif child.type in config.function_types | config.class_types | config.extra_symbol_types:
                inner = child
                break
        current = inner

    return current, decorators


# ---------------------------------------------------------------------------
# Internal: import extraction
# ---------------------------------------------------------------------------

def _extract_imports(root, config: LanguageConfig, source: bytes) -> list[str]:
    """Extract import statements as compact strings."""
    imports: list[str] = []
    for node in root.children:
        if node.type in config.import_types:
            text = _node_text(node, source).strip()
            imports.append(text)
    return imports


# ---------------------------------------------------------------------------
# Internal: formatting
# ---------------------------------------------------------------------------

def _format_line_span(symbol: SymbolInfo) -> str:
    """Format a symbol's original-file line span for drill-down navigation."""
    if symbol.start_line == symbol.end_line:
        return f"[L{symbol.start_line}]"
    return f"[L{symbol.start_line}-L{symbol.end_line}]"

def _format_structural_summary(
    path: Path,
    lines: list[str],
    symbols: list[SymbolInfo],
    imports: list[str],
) -> str:
    """Format the structural summary as compact, readable output."""
    import sys

    tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    parts: list[str] = []

    total_symbols = sum(1 + len(s.children) for s in symbols)
    export_count = sum(1 for s in symbols if s.is_exported)

    if tty:
        from skim.style import BOLD, DIM, RESET, CYAN, YELLOW, GREEN, WHITE

        # Header with colors
        header = f"{DIM}//{RESET} {BOLD}{CYAN}{path}{RESET}"
        header += f"  {DIM}{len(lines)} lines{RESET}"
        if export_count:
            header += f"  {YELLOW}{export_count} exports{RESET}"
        header += f"  {GREEN}{total_symbols} symbols{RESET}"
        parts.append(header)

        if imports:
            compact_imports = _compact_imports(imports)
            parts.append(f"{DIM}// imports: {compact_imports}{RESET}")
    else:
        header = f"// {path}  {len(lines)} lines"
        if export_count:
            header += f"  {export_count} exports"
        header += f"  {total_symbols} symbols"
        parts.append(header)

        if imports:
            compact_imports = _compact_imports(imports)
            parts.append(f"// imports: {compact_imports}")

    parts.append("")

    for sym in symbols:
        prefix = ""
        for dec in sym.decorators:
            parts.append(f"{DIM}{dec}{RESET}" if tty else dec)
        if sym.is_exported:
            prefix = "export "

        line_span = _format_line_span(sym)

        if sym.kind in ("class", "interface"):
            if tty:
                parts.append(
                    f"{BOLD}{WHITE}{prefix}{sym.signature}{RESET} "
                    f"{DIM}{line_span}{RESET}"
                )
                for method in sym.children:
                    method_span = _format_line_span(method)
                    parts.append(
                        f"  {CYAN}{method.signature}{RESET} "
                        f"{DIM}{method_span}{RESET}"
                    )
                if sym.children:
                    total_line_span = sym.end_line - sym.start_line + 1
                    parts.append(f"  {DIM}// ... {total_line_span} lines total{RESET}")
            else:
                parts.append(f"{prefix}{sym.signature}  {line_span}")
                for method in sym.children:
                    method_span = _format_line_span(method)
                    parts.append(f"  {method.signature}  {method_span}")
                if sym.children:
                    total_line_span = sym.end_line - sym.start_line + 1
                    parts.append(f"  // ... {total_line_span} lines total")
        else:
            if tty:
                parts.append(
                    f"{WHITE}{prefix}{sym.signature}{RESET} "
                    f"{DIM}{line_span}{RESET}"
                )
            else:
                parts.append(f"{prefix}{sym.signature}  {line_span}")

    return "\n".join(parts)


def _compact_imports(imports: list[str]) -> str:
    """Collapse import statements into a compact reference list."""
    import re as _re

    modules: list[str] = []
    for imp in imports:
        imp = imp.strip()

        # JS/TS: import ... from 'module'  or  import ... from "module"
        js_match = _re.search(r"""from\s+['"]([^'"]+)['"]""", imp)
        if js_match:
            modules.append(js_match.group(1))
            continue

        # Python: from X import ...
        if imp.startswith("from "):
            parts = imp.split("from ", 1)
            if len(parts) > 1:
                mod = parts[1].split(" import")[0].strip()
                modules.append(mod)
        elif "import " in imp:
            rest = imp.split("import ", 1)[1]
            for m in rest.split(","):
                m = m.strip().split(" as ")[0].strip().strip("'\"")
                if m:
                    modules.append(m)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for m in modules:
        if m not in seen:
            seen.add(m)
            unique.append(m)

    if len(unique) > 8:
        shown = ", ".join(unique[:6])
        return f"{shown}, +{len(unique) - 6} more"
    return ", ".join(unique)


# ---------------------------------------------------------------------------
# Fallback: head + tail for unsupported languages
# ---------------------------------------------------------------------------

def _head_tail_fallback(
    path: Path,
    content: str,
    lines: list[str],
    *,
    head: int = 40,
    tail: int = 20,
) -> SkimResult:
    """Return first and last N lines for unsupported file types."""
    total = len(lines)
    if total <= head + tail + 5:
        return SkimResult(content=content, mode="full", original_lines=total)

    parts = [
        f"// {path}  {total} lines (unsupported language, showing head+tail)",
        "",
        *lines[:head],
        "",
        f"// ... {total - head - tail} lines omitted ...",
        "",
        *lines[-tail:],
    ]
    summary = "\n".join(parts)
    return SkimResult(
        content=summary,
        mode="head_tail",
        original_lines=total,
        summary_lines=summary.count("\n") + 1,
    )
