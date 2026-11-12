"""Minimal S-expression reader/writer for KiCad files."""
import re

_tok = re.compile(r'\s*(\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+)')


class Sym(str):
    """Unquoted atom."""


def loads(text):
    stack, cur = [], []
    for m in _tok.finditer(text):
        t = m.group(1)
        if t == '(':
            stack.append(cur)
            cur = []
        elif t == ')':
            done, cur = cur, stack.pop()
            cur.append(done)
        elif t.startswith('"'):
            cur.append(t[1:-1].replace('\\"', '"').replace('\\\\', '\\'))
        else:
            cur.append(Sym(t))
    return cur[0]


def dumps(node, indent=0):
    if isinstance(node, list):
        simple = all(not isinstance(x, list) for x in node)
        if simple:
            return '(' + ' '.join(dumps(x) for x in node) + ')'
        pad = '\n' + '\t' * (indent + 1)
        out = '(' + dumps(node[0])
        for x in node[1:]:
            if isinstance(x, list):
                out += pad + dumps(x, indent + 1)
            else:
                out += ' ' + dumps(x)
        return out + '\n' + '\t' * indent + ')'
    if isinstance(node, Sym):
        return str(node)
    if isinstance(node, str):
        return '"' + node.replace('\\', '\\\\').replace('"', '\\"') + '"'
    return str(node)


def find(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


def first(node, key, default=None):
    r = find(node, key)
    return r[0] if r else default
