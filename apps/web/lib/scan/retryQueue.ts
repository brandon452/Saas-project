import type { RetryQueueEntry } from "@/lib/types/scan"

const DB_NAME = "scan_retry_queue"
const STORE = "entries"
const DB_VERSION = 1

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      req.result.createObjectStore(STORE, { keyPath: "id" })
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

function tx(
  db: IDBDatabase,
  mode: IDBTransactionMode,
  fn: (store: IDBObjectStore) => IDBRequest,
): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const t = db.transaction(STORE, mode)
    const req = fn(t.objectStore(STORE))
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

export async function enqueue(entry: RetryQueueEntry): Promise<void> {
  const db = await openDb()
  await tx(db, "readwrite", (s) => s.put(entry))
}

export async function dequeue(id: string): Promise<void> {
  const db = await openDb()
  await tx(db, "readwrite", (s) => s.delete(id))
}

export async function getAll(): Promise<RetryQueueEntry[]> {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const t = db.transaction(STORE, "readonly")
    const req = t.objectStore(STORE).getAll()
    req.onsuccess = () => resolve(req.result as RetryQueueEntry[])
    req.onerror = () => reject(req.error)
  })
}

export async function update(entry: RetryQueueEntry): Promise<void> {
  const db = await openDb()
  await tx(db, "readwrite", (s) => s.put(entry))
}
