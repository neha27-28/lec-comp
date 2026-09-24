import { useMemo, useRef, useState } from "react";

const API_BASE_URL = "http://127.0.0.1:8000";

function formatTime(seconds = 0) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  const minutes = Math.floor(total / 60);
  const secs = total % 60;
  return `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function getFilename(path = "") {
  return String(path).split(/[\\/]/).pop();
}

function getSlideImageUrl(jobId, path) {
  const filename = getFilename(path);
  return `${API_BASE_URL}/jobs/${jobId}/slides/${encodeURIComponent(filename)}`;
}

function App() {
  const videoRef = useRef(null);

  const [lectureUrl, setLectureUrl] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);

  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState([]);
  const [searchError, setSearchError] = useState("");

  const jobId = result?.job_id;

  const slideList = useMemo(() => {
    const slides = result?.frontend_slides || result?.slides || [];
    return Array.isArray(slides) ? slides : [];
  }, [result]);

  const handleProcess = async () => {
    setError("");
    setSearchError("");
    setResult(null);
    setSearchResults([]);

    if (!lectureUrl.trim() && !selectedFile) {
      setError("Please provide a YouTube URL or upload a video.");
      return;
    }

    setProcessing(true);

    try {
      const formData = new FormData();

      if (lectureUrl.trim()) {
        formData.append("lecture_url", lectureUrl.trim());
      }

      if (selectedFile) {
        formData.append("video", selectedFile);
      }

      const response = await fetch(`${API_BASE_URL}/process`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Something went wrong while processing the lecture."
        );
      }

      setResult(data);
    } catch (err) {
      console.error("Processing error:", err);
      setError(err.message || "Failed to process the lecture.");
    } finally {
      setProcessing(false);
    }
  };

  const handleSearch = async (event) => {
    event?.preventDefault();

    if (!jobId || !query.trim()) {
      return;
    }

    setSearching(true);
    setSearchError("");

    try {
      const response = await fetch(
        `${API_BASE_URL}/jobs/${jobId}/search?q=${encodeURIComponent(query.trim())}`
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Search failed.");
      }

      setSearchResults(data.results || []);
    } catch (err) {
      console.error("Search error:", err);
      setSearchResults([]);
      setSearchError(err.message || "Search failed.");
    } finally {
      setSearching(false);
    }
  };

  const jumpToTimestamp = (seconds) => {
    if (!videoRef.current) {
      return;
    }

    videoRef.current.currentTime = Number(seconds) || 0;
    videoRef.current.play().catch(() => {});
    videoRef.current.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  };

  const handleDownloadPdf = async () => {
    if (!jobId) return;

    try {
      const response = await fetch(
        `${API_BASE_URL}/jobs/${jobId}/slides.pdf`
      );

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.detail || "Could not download the slides PDF.");
      }

      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");

      link.href = downloadUrl;
      link.download = "lecture_slides.pdf";
      document.body.appendChild(link);
      link.click();
      link.remove();

      window.URL.revokeObjectURL(downloadUrl);
    } catch (err) {
      console.error("PDF download error:", err);
      setError(err.message || "Failed to download the slides PDF.");
    }
  };

  return (
    <div className="min-h-screen bg-warm-ivory text-charcoal">
      <header className="border-b border-dove/60">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Lecture Companion
            </h1>
            <p className="mt-1 text-sm text-charcoal/60">
              Search. Learn. Revise.
            </p>
          </div>

          <div className="flex items-center gap-2 rounded-full border border-dove bg-warm-ivory px-3 py-1.5 text-xs text-charcoal/70">
            <span className="h-2 w-2 rounded-full bg-sage" />
            Local processing
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 pb-20 pt-14">
        <section className="text-center">
          <p className="mb-4 text-sm font-medium uppercase tracking-[0.2em] text-sage">
            Lecture Companion
          </p>

          <h2 className="mx-auto max-w-3xl text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
            Turn long lectures into something you can actually find.
          </h2>

          <p className="mx-auto mt-5 max-w-2xl text-base leading-7 text-charcoal/65">
            Extract the slides, search what was taught, and jump directly to
            the relevant moment in the lecture.
          </p>
        </section>

        <section className="mx-auto mt-12 max-w-3xl rounded-3xl border border-dove bg-white/30 p-7 shadow-sm">
          <div className="mb-6">
            <h3 className="text-lg font-semibold">Add a lecture</h3>
            <p className="mt-1 text-sm text-charcoal/60">
              Paste a YouTube lecture URL or upload a video from your computer.
            </p>
          </div>

          <label className="block text-sm font-medium">Lecture URL</label>

          <div className="mt-2 flex rounded-2xl border border-dove bg-warm-ivory p-1.5 focus-within:border-sage">
            <input
              type="url"
              value={lectureUrl}
              onChange={(e) => setLectureUrl(e.target.value)}
              placeholder="https://youtube.com/..."
              className="min-w-0 flex-1 bg-transparent px-4 py-3 text-sm outline-none placeholder:text-charcoal/35"
              disabled={processing}
            />
          </div>

          <div className="my-6 flex items-center gap-4">
            <div className="h-px flex-1 bg-dove" />
            <span className="text-xs font-medium uppercase tracking-wider text-charcoal/40">
              or
            </span>
            <div className="h-px flex-1 bg-dove" />
          </div>

          <label className="group flex cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-dove bg-warm-ivory/60 px-6 py-8 text-center transition hover:border-sage">
            <div className="flex h-11 w-11 items-center justify-center rounded-full bg-sage/10 text-sage">
              ↑
            </div>

            <p className="mt-3 text-sm font-medium">Upload lecture video</p>

            <p className="mt-1 text-xs text-charcoal/50">
              MP4, WebM or other supported video format
            </p>

            <input
              type="file"
              accept="video/*"
              className="hidden"
              disabled={processing}
              onChange={(e) =>
                setSelectedFile(e.target.files?.[0] || null)
              }
            />
          </label>

          {selectedFile && (
            <div className="mt-4 rounded-xl bg-sage/10 px-4 py-3 text-sm">
              Selected:{" "}
              <span className="font-medium">{selectedFile.name}</span>
            </div>
          )}

          {error && (
            <div className="mt-4 rounded-xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <button
            onClick={handleProcess}
            disabled={processing}
            className="mt-6 w-full rounded-2xl bg-sage px-5 py-3.5 text-sm font-semibold text-warm-ivory transition hover:bg-sage/90 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {processing ? "Processing lecture..." : "Process Lecture"}
          </button>
        </section>

        {result && (
          <section className="mt-10">
            <div className="rounded-3xl border border-sage/30 bg-sage/10 p-6">
              <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
                <div>
                  <p className="text-sm font-semibold text-sage">
                    Lecture processed successfully
                  </p>
                  <p className="mt-1 text-sm text-charcoal/60">
                    {result.slides_detected || slideList.length} unique slides
                    {" · "}
                    {result.frames_extracted || 0} frames
                  </p>
                </div>

                {result.pdf_available && (
                  <button
                    onClick={handleDownloadPdf}
                    className="rounded-xl bg-charcoal px-5 py-3 text-sm font-semibold text-warm-ivory transition hover:bg-charcoal/90"
                  >
                    Download Slides PDF
                  </button>
                )}
              </div>
            </div>

            <div className="mt-8 grid gap-8 lg:grid-cols-[1.15fr_0.85fr]">
              <div className="rounded-3xl border border-dove bg-white/30 p-6">
                <div className="mb-5">
                  <p className="text-sm font-medium uppercase tracking-[0.15em] text-sage">
                    Search lecture
                  </p>
                  <h3 className="mt-2 text-2xl font-semibold">
                    What do you want to find?
                  </h3>
                </div>

                <form onSubmit={handleSearch} className="flex gap-2">
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="e.g. bubble sort adjacent elements"
                    className="min-w-0 flex-1 rounded-2xl border border-dove bg-warm-ivory px-4 py-3 text-sm outline-none focus:border-sage"
                  />

                  <button
                    type="submit"
                    disabled={searching || !query.trim()}
                    className="rounded-2xl bg-sage px-5 py-3 text-sm font-semibold text-warm-ivory disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {searching ? "..." : "Search"}
                  </button>
                </form>

                {searchError && (
                  <p className="mt-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
                    {searchError}
                  </p>
                )}

                {!searching && query && searchResults.length === 0 && !searchError && (
                  <p className="mt-8 text-sm text-charcoal/50">
                    No matching speech found.
                  </p>
                )}

                <div className="mt-6 space-y-4">
                  {searchResults.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => jumpToTimestamp(item.start_time)}
                      className="group w-full rounded-2xl border border-dove bg-warm-ivory/70 p-4 text-left transition hover:border-sage hover:bg-sage/5"
                    >
                      <div className="flex gap-4">
                        <img
                          src={getSlideImageUrl(jobId, item.image_path)}
                          alt={`Slide ${item.slide_number}`}
                          className="h-24 w-32 shrink-0 rounded-xl border border-dove object-cover"
                        />

                        <div className="min-w-0 flex-1">
                          <div className="flex items-center justify-between gap-3">
                            <span className="text-xs font-semibold uppercase tracking-wider text-sage">
                              Slide {item.slide_number}
                            </span>

                            <span className="shrink-0 rounded-full bg-charcoal px-2.5 py-1 text-xs font-medium text-warm-ivory">
                              {formatTime(item.start_time)}
                            </span>
                          </div>

                          <p className="mt-3 text-sm leading-6 text-charcoal/75">
                            {item.text}
                          </p>

                          <p className="mt-2 text-xs font-medium text-charcoal/40">
                            Click to jump to this moment →
                          </p>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="rounded-3xl border border-dove bg-charcoal p-4">
                <div className="mb-3 flex items-center justify-between px-2">
                  <div>
                    <p className="text-xs font-medium uppercase tracking-wider text-dusty-rose">
                      Lecture
                    </p>
                    <p className="mt-1 text-sm font-medium text-warm-ivory">
                      Click a search result to jump here
                    </p>
                  </div>
                </div>

                <video
                  ref={videoRef}
                  controls
                  className="w-full rounded-2xl bg-black"
                  src={`${API_BASE_URL}/jobs/${jobId}/video`}
                />
              </div>
            </div>

            {slideList.length > 0 && (
              <section className="mt-10">
                <div className="mb-5">
                  <p className="text-sm font-medium uppercase tracking-[0.15em] text-sage">
                    Extracted slides
                  </p>
                  <h3 className="mt-2 text-2xl font-semibold">
                    {slideList.length} slides from the lecture
                  </h3>
                </div>

                <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
                  {slideList.map((slide, index) => {
                    const path =
                      slide.representative_path ||
                      slide.image_path ||
                      slide._representative_path;

                    return (
                      <div
                        key={slide.slide_id || slide.slide_number || index}
                        className="overflow-hidden rounded-2xl border border-dove bg-white/30"
                      >
                        <img
                          src={getSlideImageUrl(jobId, path)}
                          alt={`Slide ${slide.slide_id || index + 1}`}
                          className="aspect-video w-full object-cover"
                        />

                        <div className="px-3 py-2 text-xs font-medium text-charcoal/60">
                          Slide {slide.slide_id || slide.slide_number || index + 1}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
            )}
          </section>
        )}

        <section className="mx-auto mt-16 max-w-4xl">
          <div className="mb-8 text-center">
            <p className="text-sm font-medium uppercase tracking-[0.15em] text-sage">
              How it works
            </p>
            <h3 className="mt-2 text-2xl font-semibold">
              One lecture. Three useful layers.
            </h3>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-2xl border border-dove bg-white/25 p-6">
              <span className="text-sm font-semibold text-sage">01</span>
              <h4 className="mt-4 font-semibold">Exact slides</h4>
              <p className="mt-2 text-sm leading-6 text-charcoal/60">
                Extract the actual slides shown during the lecture.
              </p>
            </div>

            <div className="rounded-2xl border border-dove bg-white/25 p-6">
              <span className="text-sm font-semibold text-sage">02</span>
              <h4 className="mt-4 font-semibold">Search naturally</h4>
              <p className="mt-2 text-sm leading-6 text-charcoal/60">
                Find what was said without manually scanning the recording.
              </p>
            </div>

            <div className="rounded-2xl border border-dove bg-white/25 p-6">
              <span className="text-sm font-semibold text-sage">03</span>
              <h4 className="mt-4 font-semibold">Jump to the moment</h4>
              <p className="mt-2 text-sm leading-6 text-charcoal/60">
                Open the exact point in the lecture from a search result.
              </p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
