import { GitError, parseError } from 'dugite'

/** Recognize Git's filesystem-boundary diagnostic on Linux as a missing repo. */
export function parseGitError(output: string): GitError | null {
  return (
    parseError(output) ??
    (/^fatal: not a git repository \(or any parent up to mount point .+\)\r?$/im.test(
      output
    )
      ? GitError.NotAGitRepository
      : null)
  )
}
