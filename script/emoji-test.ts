import assert from 'node:assert'
import { describe, it } from 'node:test'
import { mkdir, readFile, readdir, writeFile } from 'fs/promises'
import { join } from 'path'
import { copyEmojiAssets } from './emoji'
import { createTempDirectory } from '../app/test/helpers/temp'

describe('copyEmojiAssets', () => {
  it('packages current Unicode data without an image directory', async t => {
    const root = await createTempDirectory(t)
    const source = join(root, 'gemoji')
    const output = join(root, 'out')
    await mkdir(join(source, 'db'), { recursive: true })
    const database = JSON.stringify([{ emoji: '🐱', aliases: ['cat'] }])
    await writeFile(join(source, 'db', 'emoji.json'), database)

    copyEmojiAssets(source, output)

    assert.strictEqual(
      await readFile(join(output, 'emoji.json'), 'utf8'),
      database
    )
    assert.deepStrictEqual(await readdir(join(output, 'emoji')), [])
  })

  it('retains legacy custom images and removes Unicode fallbacks', async t => {
    const root = await createTempDirectory(t)
    const source = join(root, 'gemoji')
    const output = join(root, 'out')
    await mkdir(join(source, 'db'), { recursive: true })
    await mkdir(join(source, 'images', 'emoji', 'unicode'), { recursive: true })
    await writeFile(
      join(source, 'db', 'emoji.json'),
      JSON.stringify([
        { aliases: ['shipit'] },
        { emoji: '🐱', aliases: ['cat'] },
      ])
    )
    await writeFile(
      join(source, 'images', 'emoji', 'shipit.png'),
      'custom image'
    )
    await writeFile(
      join(source, 'images', 'emoji', 'unicode', 'cat.png'),
      'fallback'
    )

    copyEmojiAssets(source, output)

    assert.deepStrictEqual(await readdir(join(output, 'emoji')), ['shipit.png'])
    assert.strictEqual(
      await readFile(join(output, 'emoji', 'shipit.png'), 'utf8'),
      'custom image'
    )
  })

  it('rejects missing custom images before replacing previous output', async t => {
    const root = await createTempDirectory(t)
    const source = join(root, 'gemoji')
    const output = join(root, 'out')
    await mkdir(join(source, 'db'), { recursive: true })
    await mkdir(join(output, 'emoji'), { recursive: true })
    await writeFile(join(output, 'emoji', 'keep'), 'previous output')
    await writeFile(
      join(source, 'db', 'emoji.json'),
      JSON.stringify([{ aliases: ['shipit'] }])
    )

    assert.throws(
      () => copyEmojiAssets(source, output),
      /Missing custom emoji image/
    )
    assert.strictEqual(
      await readFile(join(output, 'emoji', 'keep'), 'utf8'),
      'previous output'
    )
  })

  it('rejects a missing or invalid database', async t => {
    const root = await createTempDirectory(t)
    const source = join(root, 'gemoji')
    const output = join(root, 'out')
    assert.throws(() => copyEmojiAssets(source, output), /ENOENT/)
    await mkdir(join(source, 'db'), { recursive: true })
    await writeFile(join(source, 'db', 'emoji.json'), '{}')
    assert.throws(
      () => copyEmojiAssets(source, output),
      /Invalid gemoji database/
    )
  })
})
