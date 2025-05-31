// papermind/frontend/app/page.tsx
'use client'; // Make this a Client Component

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
      let accumulatedResponse = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }
        accumulatedResponse += decoder.decode(value, { stream: true });
        setStreamingResponse(accumulatedResponse);
      }
    } catch (err: any) {
      console.error('Error fetching or processing stream:', err);
      setError(err.message || 'An unknown error occurred.');
      setStreamingResponse(''); // Clear any partial response
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
          {/* Use a <pre> tag for preserving whitespace and newlines from the stream */}
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
