"""Export visible message events only; excludes reasoning, system prompts and tool payloads."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    # Snapshot bytes once: the current session log may still be appended during this task.
    data = args.source.read_bytes()
    counts, messages, images = Counter(), [], set()
    bad = []
    for number, line in enumerate(data.decode('utf-8').splitlines(), 1):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            bad.append(number)
            continue
        p = obj.get('payload', {})
        kind = p.get('type', '')
        counts[obj.get('type', '') + ':' + kind] += 1
        if obj.get('type') != 'response_item' or kind != 'message' or p.get('role') not in ('user', 'assistant'):
            continue
        text = '\n'.join(c.get('text', '') for c in p.get('content', []) if c.get('type') in ('input_text', 'output_text', 'text'))
        if not text.strip():
            continue
        if text.startswith(('<environment_context>', '<external_codex_apps_open_page>')):
            continue
        attachments = p.get('local_images', []) or []
        for attachment in attachments:
            if isinstance(attachment, str):
                images.add(attachment)
        messages.append(dict(id=f'M{len(messages)+1:04d}', source_line=number,
                             timestamp=obj.get('timestamp'), role=p['role'], phase=p.get('phase'),
                             text=text, local_images=attachments))
    args.destination.mkdir(parents=True, exist_ok=True)
    output = args.destination / 'visible_messages.jsonl'
    output.write_text(''.join(json.dumps(m, ensure_ascii=False)+'\n' for m in messages), encoding='utf-8')
    manifest = dict(thread_id='01a12dd0-f377-7de2-9266-255836ab4907',
                    source=str(args.source), source_sha256=hashlib.sha256(data).hexdigest(),
                    source_bytes=len(data), source_lines=len(data.decode('utf-8').splitlines()),
                    event_counts=dict(counts), exported_messages=len(messages),
                    parse_error_lines=bad, first_timestamp=messages[0]['timestamp'] if messages else None,
                    last_timestamp=messages[-1]['timestamp'] if messages else None,
                    boundary='Visible response messages only. Images remain references; no image OCR or hidden reasoning export.')
    (args.destination / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    for m in messages:
        if m['role'] == 'user':
            text = m['text']
            if '## My request:' in text:
                text = text.split('## My request:', 1)[1]
            if text.strip():
                print(m['id'], m['timestamp'], text.replace('\n', ' ')[:180])


if __name__ == '__main__':
    main()
