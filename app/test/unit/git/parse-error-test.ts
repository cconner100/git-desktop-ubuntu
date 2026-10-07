import assert from 'node:assert'
import { describe, it } from 'node:test'
import { GitError } from 'dugite'
import { parseGitError } from '../../../src/lib/git/parse-error'

describe('parseGitError', () => {
  it('recognizes the Linux filesystem-boundary diagnostic', () => {
    assert.strictEqual(
      parseGitError(
        'fatal: not a git repository (or any parent up to mount point /)\n' +
          'Stopping at filesystem boundary (GIT_DISCOVERY_ACROSS_FILESYSTEM not set).\n'
      ),
      GitError.NotAGitRepository
    )
  })

  it('handles mount paths with spaces and CRLF output', () => {
    assert.strictEqual(
      parseGitError(
        'fatal: not a git repository (or any parent up to mount point /media/Shared Files)\r\n'
      ),
      GitError.NotAGitRepository
    )
  })

  it('preserves the ordinary missing-repository classification', () => {
    assert.strictEqual(
      parseGitError(
        'fatal: not a git repository (or any of the parent directories): .git\n'
      ),
      GitError.NotAGitRepository
    )
  })

  it('leaves unrelated and unrecognized errors unclassified', () => {
    assert.strictEqual(parseGitError('fatal: invalid gitfile format\n'), null)
    assert.strictEqual(parseGitError('some unrelated output\n'), null)
  })
})
