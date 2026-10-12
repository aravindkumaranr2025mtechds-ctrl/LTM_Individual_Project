import type {
  AssistantResponse,
} from '../types/assistant'

export async function assistantTurn(
  payload: unknown,
): Promise<AssistantResponse> {

  const response = await fetch(
    '/assistant/turn',
    {
      method: 'POST',

      headers: {
        'Content-Type': 'application/json',
      },

      body: JSON.stringify(payload),
    },
  )

  const data = await response.json().catch(
    () => null,
  )

  if (!response.ok) {
    const detail =
      data &&
      typeof data === 'object' &&
      'detail' in data
        ? String(data.detail)
        : `Request failed with HTTP ${response.status}`

    throw new Error(detail)
  }

  return data as AssistantResponse
}

export function sourcePageUrl(
  documentId: string,
  pageNumber: number,
) {
  return (
    '/assistant/source-page/' +
    encodeURIComponent(documentId) +
    '/' +
    encodeURIComponent(String(pageNumber))
  )
}
