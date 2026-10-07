/* eslint-disable no-sync */
import { cpSync, readFileSync, rmSync, statSync } from 'fs'
import { dirname, join } from 'path'
import { getCopilotRuntimePath } from '../app/src/lib/copilot-runtime'

/** Keep the FFI loader and its matching native package together outside webpack. */
export function copyKoffiDependency(
  nodeModulesRoot: string,
  destination: string,
  platform: NodeJS.Platform,
  arch: string
): void {
  const source = join(nodeModulesRoot, 'koffi')
  const nativePackage = `@koromix/koffi-${platform}-${arch}`
  const nativeSource = join(nodeModulesRoot, nativePackage)
  const manifest = JSON.parse(
    readFileSync(join(source, 'package.json'), 'utf8')
  )
  const nativeManifest = JSON.parse(
    readFileSync(join(nativeSource, 'package.json'), 'utf8')
  )
  if (manifest.version !== nativeManifest.version) {
    throw new Error(`Mismatched Koffi native package: ${nativePackage}`)
  }
  for (const [from, to] of [
    [source, join(destination, 'koffi')],
    [nativeSource, join(destination, nativePackage)],
  ]) {
    rmSync(to, { recursive: true, force: true })
    cpSync(from, to, { recursive: true, verbatimSymlinks: true })
  }
  if (platform === 'linux') {
    // These Linux packages target glibc. Loading/checking musl binaries on
    // Ubuntu is invalid; retain the matching glibc prebuild and loader.
    rmSync(join(destination, nativePackage, `musl_${arch}`), {
      recursive: true,
      force: true,
    })
  }
}

/** Copy the SDK's target-specific runtime and its companion assets. */
export function copyCopilotDependency(
  nodeModulesRoot: string,
  destination: string,
  platform: NodeJS.Platform,
  arch: string
): void {
  const source = join(
    nodeModulesRoot,
    '@github',
    `copilot-sdk-${platform}-${arch}`
  )
  const runtimePath = getCopilotRuntimePath(source, platform, arch)

  // Both files are required by the standalone runtime. Fail the build rather
  // than shipping a client that cannot start when optional packages are missing.
  for (const file of [
    runtimePath,
    join(dirname(runtimePath), 'runtime.node'),
  ]) {
    const info = statSync(file)
    if (!info.isFile() || info.size === 0) {
      throw new Error(`Missing or empty Copilot runtime file: ${file}`)
    }
  }

  // SDK platform packages already exclude other platforms and CLI-only assets.
  // Preserve their layout: the wrapper loads runtime.node and adjacent assets.
  rmSync(destination, { recursive: true, force: true })
  cpSync(source, destination, { recursive: true, verbatimSymlinks: true })
}
