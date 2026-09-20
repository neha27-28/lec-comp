import { useState } from "react";

function App() {
  const [lectureUrl, setLectureUrl] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);

  const handleProcess = () => {
    if (!lectureUrl && !selectedFile) {
      return;
    }

    // Backend integration will be connected here.
    console.log("Lecture ready for processing");
  };

  return (
    <div className="min-h-screen bg-warm-ivory text-charcoal">

      {/* Header */}
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


      {/* Main */}
      <main className="mx-auto max-w-5xl px-6 pb-20 pt-16">

        {/* Hero */}
        <section className="text-center">

          <p className="mb-4 text-sm font-medium uppercase tracking-[0.2em] text-sage">
            Lecture Companion
          </p>

          <h2 className="mx-auto max-w-3xl text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
            Turn long lectures into something you can actually find.
          </h2>

          <p className="mx-auto mt-5 max-w-2xl text-base leading-7 text-charcoal/65">
            Extract the exact slides from a lecture, search what was taught
            in plain language, and quickly return to the relevant moment.
          </p>

        </section>


        {/* Input Card */}
        <section className="mx-auto mt-12 max-w-3xl rounded-3xl border border-dove bg-white/30 p-7 shadow-sm">

          <div className="mb-6">
            <h3 className="text-lg font-semibold">
              Add a lecture
            </h3>

            <p className="mt-1 text-sm text-charcoal/60">
              Paste a YouTube lecture URL or upload a video from your computer.
            </p>
          </div>


          {/* URL */}
          <label className="block text-sm font-medium">
            Lecture URL
          </label>

          <div className="mt-2 flex rounded-2xl border border-dove bg-warm-ivory p-1.5 focus-within:border-sage">

            <input
              type="url"
              value={lectureUrl}
              onChange={(e) => setLectureUrl(e.target.value)}
              placeholder="https://youtube.com/..."
              className="min-w-0 flex-1 bg-transparent px-4 py-3 text-sm outline-none placeholder:text-charcoal/35"
            />

          </div>


          {/* Divider */}
          <div className="my-6 flex items-center gap-4">
            <div className="h-px flex-1 bg-dove" />
            <span className="text-xs font-medium uppercase tracking-wider text-charcoal/40">
              or
            </span>
            <div className="h-px flex-1 bg-dove" />
          </div>


          {/* Upload */}
          <label className="group flex cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-dove bg-warm-ivory/60 px-6 py-8 text-center transition hover:border-sage">

            <div className="flex h-11 w-11 items-center justify-center rounded-full bg-sage/10 text-sage">
              ↑
            </div>

            <p className="mt-3 text-sm font-medium">
              Upload lecture video
            </p>

            <p className="mt-1 text-xs text-charcoal/50">
              MP4, WebM or other supported video format
            </p>

            <input
              type="file"
              accept="video/*"
              className="hidden"
              onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
            />

          </label>


          {/* Selected file */}
          {selectedFile && (
            <div className="mt-4 rounded-xl bg-sage/10 px-4 py-3 text-sm text-charcoal">
              Selected:{" "}
              <span className="font-medium">
                {selectedFile.name}
              </span>
            </div>
          )}


          {/* Process */}
          <button
            onClick={handleProcess}
            className="mt-6 w-full rounded-2xl bg-sage px-5 py-3.5 text-sm font-semibold text-warm-ivory transition hover:bg-sage/90 active:scale-[0.99]"
          >
            Process Lecture
          </button>

        </section>


        {/* What happens */}
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
              <span className="text-sm font-semibold text-sage">
                01
              </span>

              <h4 className="mt-4 font-semibold">
                Exact slides
              </h4>

              <p className="mt-2 text-sm leading-6 text-charcoal/60">
                Extract the actual slides shown during the lecture rather
                than generating a summary of them.
              </p>
            </div>


            <div className="rounded-2xl border border-dove bg-white/25 p-6">
              <span className="text-sm font-semibold text-sage">
                02
              </span>

              <h4 className="mt-4 font-semibold">
                Search naturally
              </h4>

              <p className="mt-2 text-sm leading-6 text-charcoal/60">
                Search for something you remember from the lecture without
                manually scanning the entire recording.
              </p>
            </div>


            <div className="rounded-2xl border border-dove bg-white/25 p-6">
              <span className="text-sm font-semibold text-sage">
                03
              </span>

              <h4 className="mt-4 font-semibold">
                Process locally
              </h4>

              <p className="mt-2 text-sm leading-6 text-charcoal/60">
                Lecture processing is designed to run on the student's own
                machine instead of sending lecture content to a cloud AI
                service.
              </p>
            </div>

          </div>

        </section>

      </main>

    </div>
  );
}

export default App;