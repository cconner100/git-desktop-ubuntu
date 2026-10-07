/* eslint-disable no-sync */
import {
  cpSync,
  existsSync,
  mkdirSync,
  readFileSync,
  rmSync,
  statSync,
} from 'fs'
import { join } from 'path'

interface IGemojiDefinition {
  readonly emoji?: string
  readonly aliases: ReadonlyArray<string>
}

/** Package legacy custom images or a current, Unicode-only gemoji database. */
export function copyEmojiAssets(gemojiRoot: string, outRoot: string): void {
  const database = join(gemojiRoot, 'db', 'emoji.json')
  const definitions: ReadonlyArray<IGemojiDefinition> = JSON.parse(
    readFileSync(database, 'utf8')
  )
  if (!Array.isArray(definitions)) {
    throw new Error(`Invalid gemoji database: ${database}`)
  }

  const images = join(gemojiRoot, 'images', 'emoji')
  // Custom entries still require real image assets; never silently omit them.
  for (const definition of definitions.filter(emoji => !emoji.emoji)) {
    const image = join(images, `${definition.aliases[0]}.png`)
    if (!existsSync(image) || statSync(image).size === 0) {
      throw new Error(`Missing custom emoji image: ${image}`)
    }
  }

  const destination = join(outRoot, 'emoji')
  rmSync(destination, { recursive: true, force: true })
  if (existsSync(images)) {
    cpSync(images, destination, { recursive: true, verbatimSymlinks: true })
    // Unicode characters use system fonts rather than fallback images.
    rmSync(join(destination, 'unicode'), { recursive: true, force: true })
  } else {
    mkdirSync(destination, { recursive: true })
  }
  cpSync(database, join(outRoot, 'emoji.json'))
}
