const assert = require('node:assert');
const test = require('node:test');

const { parseLine, tokenize, parseFetchItems, parseSequenceSet, isInSequenceSet } = require('../src/parser');
const { getFolder } = require('../src/folders');

test('parseLine and tokenize handle basic IMAP commands', () => {
  assert.deepStrictEqual(parseLine('A1 LOGIN "user@example.com" "p a s s"'), {
    tag: 'A1',
    command: 'LOGIN',
    args: '"user@example.com" "p a s s"',
  });
  assert.deepStrictEqual(tokenize('"user@example.com" "p a s s"'), ['user@example.com', 'p a s s']);
});

test('parseFetchItems handles common client requests', () => {
  const items = parseFetchItems('UID FLAGS BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT)]');
  assert.deepStrictEqual(items[0], { type: 'UID' });
  assert.deepStrictEqual(items[1], { type: 'FLAGS' });
  assert.strictEqual(items[2].type, 'BODY_SECTION');
  assert.strictEqual(items[2].peek, true);
  assert.strictEqual(items[2].section, 'HEADER.FIELDS');
  assert.deepStrictEqual(items[2].fields, ['FROM', 'TO', 'SUBJECT']);
});

test('sequence set supports ranges and wildcard', () => {
  const ranges = parseSequenceSet('1,3:5,10:*');
  assert.strictEqual(isInSequenceSet(1, ranges), true);
  assert.strictEqual(isInSequenceSet(4, ranges), true);
  assert.strictEqual(isInSequenceSet(9, ranges), false);
  assert.strictEqual(isInSequenceSet(999, ranges), true);
});

test('folder mappings protect per-account mailbox boundaries', () => {
  assert.deepStrictEqual(getFolder('inbox').filter('u@example.com'), {
    to_addresses: 'u@example.com',
    is_deleted: { $ne: true },
  });
  assert.deepStrictEqual(getFolder('Sent').filter('u@example.com'), {
    from_address: 'u@example.com',
  });
  assert.strictEqual(getFolder('Unknown'), null);
});
