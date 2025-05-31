export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const q = searchParams.get('q');

  if (!q) {
    return new Response('Missing query parameter "q"', { status: 400 });
  }

  const backendUrl = process.env.BACKEND_URL || 'http://127.0.0.1:8000';

  try {
    const response = await fetch(`${backendUrl}/rag_stream?q=${encodeURIComponent(q)}`);

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`Backend error: ${response.status} ${errorText}`);
      return new Response(`Error from backend: ${errorText}`, { status: response.status });
    }

    if (!response.body) {
      return new Response('Backend returned no stream body', { status: 500 });
    }

    const stream = new ReadableStream({
      async start(controller) {
        const reader = response.body!.getReader();
        const decoder = new TextDecoder();

        function push() {
          reader.read().then(({ done, value }) => {
            if (done) {
              controller.close();
              return;
            }
            controller.enqueue(decoder.decode(value, { stream: true }));
            push();
          }).catch(err => {
            console.error('Error reading from backend stream:', err);
            controller.error(err);
          });
        }
        push();
      }
    });

    return new Response(stream, {
      headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
    });

  } catch (error) {
    console.error('Error fetching from backend:', error);
    return new Response('Error fetching from backend', { status: 500 });
  }
}
