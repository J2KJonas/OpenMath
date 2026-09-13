/**
 * OpenMath Pyodide Web Worker
 * Manages client-side Python WebAssembly runtime with SymPy, NumPy, and OpenMath cas_engine.
 */

// Import Pyodide script inside worker
importScripts("https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js");

let pyodide = null;
let casBridge = null;
let isInitialized = false;
let pendingMessages = [];

function executeParseDocument(data) {
  try {
    pyodide.globals.set("_doc_content_input", data.content || "");
    const docJson = pyodide.runPython(`
json.dumps(cas_bridge.parse_worksheet_document(_doc_content_input))
`);
    const parsedDoc = JSON.parse(docJson);
    postMessage({
      type: "DOCUMENT_PARSED",
      ...parsedDoc
    });
  } catch (err) {
    postMessage({
      type: "DOCUMENT_PARSED",
      cells: [],
      error: `Document Parse Error: ${err.message}`
    });
  }
}

// List of cas_engine modules to load
const CAS_ENGINE_FILES = [
  "__init__.py",
  "engine.py",
  "parser.py",
  "formatter.py",
  "plot_engine.py",
  "embedded.py",
  "error_suggester.py",
  "function_guide.py",
  "typesetting_parser.py",
  "units.py",
  "wheeler.py",
  "mw_importer.py"
];

async function initPyodideRuntime(basePath = "../") {
  try {
    postMessage({ type: "STATUS", status: "loading", message: "Starting Python WebAssembly runtime..." });

    pyodide = await loadPyodide({
      indexURL: "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/"
    });

    postMessage({ type: "STATUS", status: "loading", message: "Loading SymPy & NumPy math packages..." });
    await pyodide.loadPackage(["sympy", "numpy"]);

    postMessage({ type: "STATUS", status: "loading", message: "Mounting OpenMath CAS engine..." });

    // Set up directories in virtual filesystem
    pyodide.FS.mkdirTree("/home/pyodide/cas_engine");

    // Attempt to load bundled bundle JSON first, or fetch files individually
    let loadedBundle = false;
    try {
      const bundleResp = await fetch(`${basePath}cas_bundle.json`);
      if (bundleResp.ok) {
        const bundle = await bundleResp.json();
        for (const [filename, content] of Object.entries(bundle)) {
          if (filename.startsWith("cas_engine/")) {
            const relName = filename.replace("cas_engine/", "");
            pyodide.FS.writeFile(`/home/pyodide/cas_engine/${relName}`, content);
          } else {
            pyodide.FS.writeFile(`/home/pyodide/${filename}`, content);
          }
        }
        loadedBundle = true;
      }
    } catch (e) {
      console.warn("Bundle not found, loading individual files:", e);
    }

    if (!loadedBundle) {
      // Fetch each cas_engine file directly
      for (const file of CAS_ENGINE_FILES) {
        try {
          const resp = await fetch(`${basePath}cas_engine/${file}`);
          if (resp.ok) {
            const text = await resp.text();
            pyodide.FS.writeFile(`/home/pyodide/cas_engine/${file}`, text);
          }
        } catch (err) {
          console.error(`Failed to fetch cas_engine/${file}`, err);
        }
      }

      // Fetch bridge file
      try {
        const bridgeResp = await fetch(`${basePath}py/cas_bridge.py`);
        if (bridgeResp.ok) {
          const bridgeText = await bridgeResp.text();
          pyodide.FS.writeFile("/home/pyodide/cas_bridge.py", bridgeText);
        }
      } catch (err) {
        console.error("Failed to fetch py/cas_bridge.py", err);
      }
    }

    // Initialize Python environment and import bridge
    pyodide.runPython(`
import sys
if "/home/pyodide" not in sys.path:
    sys.path.insert(0, "/home/pyodide")
import cas_bridge
import json
`);

    const infoJson = pyodide.runPython("json.dumps(cas_bridge.get_system_info())");
    const sysInfo = JSON.parse(infoJson);

    isInitialized = true;
    postMessage({
      type: "READY",
      status: "ready",
      message: "OpenMath CAS engine is ready.",
      info: sysInfo
    });

    // Drain queued requests
    while (pendingMessages.length > 0) {
      const queued = pendingMessages.shift();
      if (queued && queued.type === "PARSE_DOCUMENT") {
        executeParseDocument(queued);
      }
    }
  } catch (err) {
    console.error("Error initializing Pyodide:", err);
    postMessage({
      type: "ERROR",
      status: "error",
      message: `Failed to initialize CAS engine: ${err.message}`
    });
  }
}

self.onmessage = async function (e) {
  const data = e.data;
  if (!data || !data.type) return;

  switch (data.type) {
    case "INIT":
      if (!isInitialized) {
        await initPyodideRuntime(data.basePath || "");
      } else {
        postMessage({ type: "READY", status: "ready" });
      }
      break;

    case "EVALUATE":
      if (!isInitialized) {
        postMessage({
          type: "RESULT",
          id: data.id,
          error: "CAS engine is still initializing. Please wait a moment..."
        });
        return;
      }
      try {
        // Pass expression and precision safely via Python globals
        pyodide.globals.set("_eval_expr_input", data.expr || "");
        pyodide.globals.set("_eval_prec_input", parseInt(data.precision || 6, 10));

        const resultJson = pyodide.runPython(`
json.dumps(cas_bridge.evaluate_expression(_eval_expr_input, precision=_eval_prec_input))
`);
        const parsed = JSON.parse(resultJson);
        postMessage({
          type: "RESULT",
          id: data.id,
          ...parsed
        });
      } catch (err) {
        postMessage({
          type: "RESULT",
          id: data.id,
          error: `Worker Error: ${err.message}`
        });
      }
      break;

    case "RESET":
      if (isInitialized) {
        pyodide.runPython("cas_bridge.reset_workspace()");
        postMessage({ type: "RESET_DONE", status: "success" });
      }
      break;

    case "WHOS":
      if (isInitialized) {
        const varsJson = pyodide.runPython("json.dumps(cas_bridge.get_variables_list())");
        postMessage({ type: "WHOS_RESULT", vars: JSON.parse(varsJson) });
      }
      break;

    case "PARSE_DOCUMENT":
      if (!isInitialized) {
        pendingMessages.push(data);
        postMessage({
          type: "STATUS",
          status: "loading",
          message: "Parsing worksheet document (waiting for CAS engine)..."
        });
        return;
      }
      executeParseDocument(data);
      break;

    default:
      console.warn("Unknown message type:", data.type);
  }
};
