'use client';

import { useState, FormEvent } from 'react';

export default function Home() {
  const [query, setQuery] = useState<string>('');
  const [streamingResponse, setStreamingResponse] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!query.trim()) {
      setError('Please enter a query.');
      return;
    }

    setIsLoading(true);
    setStreamingResponse('');
    setError(null);

    try {
      const response = await fetch(`/rag?q=${encodeURIComponent(query)}`);

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to fetch stream: ${response.status} ${errorText || ''}`);
      }

      if (!response.body) {
        throw new Error('Response body is null');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      const eventSeparator = "\n\n";
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }
        buffer += decoder.decode(value, { stream: true });

        let eventEndIndex = buffer.indexOf(eventSeparator);
        while (eventEndIndex !== -1) {
          const rawEvent = buffer.substring(0, eventEndIndex);
          buffer = buffer.substring(eventEndIndex + eventSeparator.length);

          if (rawEvent.startsWith("data: ")) {
            const jsonData = rawEvent.substring("data: ".length);
            try {
                // Assuming the backend sends plain text tokens directly, not JSON strings for each token
                // If it was JSON: const parsedToken = JSON.parse(jsonData);
                // For plain text:
                setStreamingResponse(prev => prev + jsonData);
            } catch (e) {
                console.error("Failed to parse JSON from stream or handle data: ", jsonData, e);
            }
          }
          eventEndIndex = buffer.indexOf(eventSeparator);
        }
      }
      // Process any remaining data in the buffer after the loop (if stream ends without \n\n)
      if (buffer.startsWith("data: ")) {
        const jsonData = buffer.substring("data: ".length);
        setStreamingResponse(prev => prev + jsonData);
      }


    } catch (err: any) {
      console.error('Error fetching or processing stream:', err);
      setError(err.message || 'An unknown error occurred.');
      setStreamingResponse('');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6 font-sans">
      <h1 className="text-3xl font-bold mb-6 text-center text-gray-800">PaperMind</h1>

      <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-2 mb-6">
        <input
          name="q"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="flex-1 border border-gray-300 rounded-md p-3 text-gray-700 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-shadow duration-150"
          placeholder="Ask your PDF a question..."
          disabled={isLoading}
        />
        <button
          type="submit"
          className="bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-md px-6 py-3 transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
          disabled={isLoading}
        >
          {isLoading ? 'Asking...' : 'Ask'}
        </button>
      </form>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-md relative mb-4" role="alert">
          <strong className="font-bold">Error: </strong>
          <span className="block sm:inline">{error}</span>
        </div>
      )}

      {streamingResponse && (
        <div className="bg-gray-50 p-4 border border-gray-200 rounded-md shadow">
          <h2 className="text-xl font-semibold mb-3 text-gray-700">Answer:</h2>
          <pre className="whitespace-pre-wrap break-words text-gray-800 leading-relaxed">
            {streamingResponse}
          </pre>
        </div>
      )}

      {!isLoading && !streamingResponse && !error && (
         <div className="text-center text-gray-500 pt-8">
           <p>Enter a query above to get started.</p>
           <p className="mt-2 text-sm">Ensure your PaperMind backend server is running and PDFs are indexed.</p>
         </div>
      )}
    </div>
  );
}
