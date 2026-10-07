import assert from 'node:assert'
import { describe, it } from 'node:test'
import { chmod, mkdir, readFile, readdir, stat, writeFile } from 'fs/promises'
import { dirname, join, relative } from 'path'
import { copyCopilotDependency, copyKoffiDependency } from './copilot'
import { createTempDirectory } from '../app/test/helpers/temp'
import { getCopilotRuntimePath } from '../app/src/lib/copilot-runtime'

describe('copyKoffiDependency', () => {
  it('copies the loader with its matching native package for Ubuntu', async t => {
    const root = await createTempDirectory(t)
    const source = join(root, 'node_modules')
    const output = join(root, 'out', 'node_modules')
    const native = join(source, '@koromix', 'koffi-linux-x64')
    await mkdir(join(source, 'koffi'), { recursive: true })
    await mkdir(join(native, 'linux_x64'), { recursive: true })
    await mkdir(join(native, 'musl_x64'), { recursive: true })
    await writeFile(
      join(source, 'koffi', 'package.json'),
      '{"version":"3.2.1"}'
    )
    await writeFile(join(source, 'koffi', 'index.cjs'), 'loader')
    await writeFile(join(native, 'package.json'), '{"version":"3.2.1"}')
    await writeFile(join(native, 'linux_x64', 'koffi.node'), 'native module')
    await writeFile(join(native, 'musl_x64', 'koffi.node'), 'musl module')

    copyKoffiDependency(source, output, 'linux', 'x64')

    assert.strictEqual(
      await readFile(join(output, 'koffi', 'index.cjs'), 'utf8'),
      'loader'
    )
    assert.strictEqual(
      await readFile(
        join(output, '@koromix', 'koffi-linux-x64', 'linux_x64', 'koffi.node'),
        'utf8'
      ),
      'native module'
    )
    assert.ok(
      !(await readdir(join(output, '@koromix', 'koffi-linux-x64'))).includes(
        'musl_x64'
      )
    )
  })

  it('rejects a mismatched native package before replacing output', async t => {
    const root = await createTempDirectory(t)
    const source = join(root, 'node_modules')
    const output = join(root, 'out', 'node_modules')
    await mkdir(join(source, 'koffi'), { recursive: true })
    await mkdir(join(source, '@koromix', 'koffi-linux-x64'), {
      recursive: true,
    })
    await mkdir(output, { recursive: true })
    await writeFile(join(output, 'keep'), 'previous output')
    await writeFile(
      join(source, 'koffi', 'package.json'),
      '{"version":"3.2.1"}'
    )
    await writeFile(
      join(source, '@koromix', 'koffi-linux-x64', 'package.json'),
      '{"version":"3.1.0"}'
    )

    assert.throws(
      () => copyKoffiDependency(source, output, 'linux', 'x64'),
      /Mismatched Koffi native package/
    )
    assert.strictEqual(
      await readFile(join(output, 'keep'), 'utf8'),
      'previous output'
    )
  })
})

describe('copyCopilotDependency', () => {
  for (const platform of ['darwin', 'win32', 'linux'] as const) {
    for (const arch of ['arm64', 'x64']) {
      it(`copies the ${platform}-${arch} runtime and assets`, async t => {
        const root = await createTempDirectory(t)
        const nodeModules = join(root, 'node_modules')
        const source = join(
          nodeModules,
          '@github',
          `copilot-sdk-${platform}-${arch}`
        )
        const destination = join(root, 'copilot')
        const runtime = getCopilotRuntimePath(source, platform, arch)
        assert.strictEqual(
          relative(source, runtime),
          join(
            'prebuilds',
            `${platform}-${arch}`,
            platform === 'win32' ? 'copilot-runtime.exe' : 'copilot-runtime'
          )
        )

        const files = [
          relative(source, runtime),
          join('prebuilds', `${platform}-${arch}`, 'runtime.node'),
          join('ripgrep', 'bin', `${platform}-${arch}`, 'rg'),
          join('sdk', 'index.js'),
          'package.json',
        ]
        for (const file of files) {
          await mkdir(dirname(join(source, file)), { recursive: true })
          await writeFile(join(source, file), file)
        }
        await chmod(runtime, 0o755)
        await mkdir(destination)
        await writeFile(join(destination, 'index.js'), 'old CLI entry point')

        copyCopilotDependency(nodeModules, destination, platform, arch)

        for (const file of files) {
          assert.strictEqual(
            await readFile(join(destination, file), 'utf8'),
            file
          )
        }
        assert.ok(!(await readdir(destination)).includes('index.js'))
        assert.deepStrictEqual(await readdir(join(destination, 'prebuilds')), [
          `${platform}-${arch}`,
        ])
        if (process.platform !== 'win32') {
          assert.strictEqual(
            (await stat(getCopilotRuntimePath(destination, platform, arch)))
              .mode & 0o777,
            0o755
          )
        }
      })
    }
  }

  it('fails when the target optional package is missing', async t => {
    const root = await createTempDirectory(t)
    assert.throws(
      () => copyCopilotDependency(root, join(root, 'out'), 'win32', 'x64'),
      /ENOENT/
    )
  })

  for (const missingFile of ['copilot-runtime', 'runtime.node']) {
    it(`fails before replacing output when ${missingFile} is missing or empty`, async t => {
      const root = await createTempDirectory(t)
      const source = join(root, '@github', 'copilot-sdk-darwin-arm64')
      const prebuilds = join(source, 'prebuilds', 'darwin-arm64')
      const destination = join(root, 'out')
      await mkdir(prebuilds, { recursive: true })
      await mkdir(destination)
      await writeFile(join(destination, 'keep'), 'existing output')
      for (const file of ['copilot-runtime', 'runtime.node']) {
        if (file !== missingFile) {
          await writeFile(join(prebuilds, file), 'runtime')
        }
      }

      assert.throws(
        () => copyCopilotDependency(root, destination, 'darwin', 'arm64'),
        /ENOENT/
      )
      await writeFile(join(prebuilds, missingFile), '')
      assert.throws(
        () => copyCopilotDependency(root, destination, 'darwin', 'arm64'),
        /Missing or empty Copilot runtime file/
      )
      assert.strictEqual(
        await readFile(join(destination, 'keep'), 'utf8'),
        'existing output'
      )
    })
  }
})
