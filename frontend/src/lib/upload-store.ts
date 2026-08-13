/**
 * Hands files picked on one screen (dashboard dropzone, documents header) over
 * to the Upload & OCR pipeline screen without a backend round-trip.
 *
 * Deliberately in-memory: the real upload happens through
 * `api().uploadDocument()` once a backend is connected.
 */

let stagedFiles: File[] = [];

export function stageUploads(files: File[]) {
  stagedFiles = files;
}

export function takeStagedUploads(): File[] {
  const files = stagedFiles;
  stagedFiles = [];
  return files;
}
