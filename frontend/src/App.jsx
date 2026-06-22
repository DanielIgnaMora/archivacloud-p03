import { useState, useEffect } from 'react';
import axios from 'axios';

function App() {
  const [file, setFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [status, setStatus] = useState("Esperando selección de archivo...");
  const [files, setFiles] = useState([]);

  // Parámetros únicos Pareja P-03 (Anexo B)
  const BUCKET_NAME = "archivacloud-p03dm";
  const REGION = "us-west-2";
  const MAX_SIZE = 20 * 1024 * 1024; // 20 MB [2]

  useEffect(() => {
    fetchFiles();
  }, []);

  // CU-02: Listar archivos [3]
  const fetchFiles = async () => {
    try {
      const response = await axios.get("http://localhost:8000/api/files");
      setFiles(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      console.error("Error al listar archivos:", error);
      setStatus("Error al conectar con el backend.");
    }
  };

  // Feature Extra P-03: Función para generar el hash SHA-256 [2, 4]
  const calculateHash = async (fileToHash) => {
    const buffer = await fileToHash.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  };

  // CU-05: Validar tipo (MP3/WAV) y tamaño (20MB) [2, 3]
  const handleFileChange = (e) => {
    const selectedFile = e.target.files;
    if (!selectedFile) return;

    const name = selectedFile.name.toLowerCase();
    const isAllowed = name.endsWith('.mp3') || name.endsWith('.wav');

    if (!isAllowed) {
      setStatus(`Error: El archivo "${selectedFile.name}" no es MP3 o WAV.`);
      setFile(null);
      return;
    }

    if (selectedFile.size > MAX_SIZE) {
      setStatus("Error: El archivo supera el límite de 20 MB.");
      setFile(null);
      return;
    }

    setFile(selectedFile);
    setStatus(`Archivo listo: ${selectedFile.name}`);
  };

  // CU-01: Subida vía Presigned URL con Feature Extra [3, 5]
  const handleUpload = async () => {
    if (!file) return;
    
    try {
      setStatus("Calculando integridad (SHA-256)...");
      const fileHash = await calculateHash(file); // Feature Extra P-03 [2]

      setStatus("Solicitando permiso a S3...");
      setUploadProgress(0);

      // Enviar hash al backend para guardarlo como metadato [6]
      const { data } = await axios.post("http://localhost:8000/api/upload/presigned-url", {
        fileName: file.name,
        fileType: file.type || "audio/mpeg",
        fileHash: fileHash 
      });

      // Subida directa a S3 con barra de progreso
      await axios.put(data.presignedUrl, file, {
        headers: { "Content-Type": file.type || "audio/mpeg" },
        onUploadProgress: (p) => setUploadProgress(Math.round((p.loaded * 100) / p.total))
      });

      setStatus("¡Subida exitosa e integridad verificada!");
      setFile(null);
      setUploadProgress(0);
      fetchFiles();
    } catch (error) {
      // SEC-07: Manejo de errores sin trazas técnicas [7]
      setStatus("Error en el proceso de subida o cálculo de hash.");
    }
  };

  // CU-04: Eliminar archivo con confirmación [3]
  const handleDelete = async (key) => {
    if (!window.confirm("¿Está seguro de eliminar este archivo? Esta acción es irreversible.")) return;

    try {
      setStatus("Eliminando archivo...");
      await axios.delete(`http://localhost:8000/api/files/${key}`);
      setStatus("Archivo eliminado exitosamente.");
      fetchFiles();
    } catch (error) {
      setStatus("Error al intentar eliminar el archivo.");
    }
  };

  return (
    <div style={{ padding: "40px", backgroundColor: "#121212", color: "white", minHeight: "100vh", fontFamily: "sans-serif" }}>
      <center>
        <h1>ArchivaCloud Portal - P-03</h1>
        <p>Región: <strong>{REGION}</strong> | Bucket: <strong>{BUCKET_NAME}</strong></p>
      </center>

      <div style={{ border: "1px solid #333", padding: "20px", margin: "20px 0", borderRadius: "10px", backgroundColor: "#1e1e1e" }}>
        <h3>Subir Nuevo Audio (MP3/WAV - Máx 20MB)</h3>
        <input type="file" accept=".mp3,.wav" onChange={handleFileChange} />
        <button onClick={handleUpload} disabled={!file} style={{ marginLeft: "10px", padding: "8px 20px" }}>
          Subir a S3
        </button>

        {uploadProgress > 0 && (
          <div style={{ width: "100%", backgroundColor: "#444", marginTop: "15px", borderRadius: "5px" }}>
            <div style={{ width: `${uploadProgress}%`, height: "20px", backgroundColor: "#4caf50", textAlign: "center", color: "black", fontWeight: "bold" }}>
              {uploadProgress}%
            </div>
          </div>
        )}
        <p style={{ marginTop: "10px" }}><strong>Status:</strong> {status}</p>
      </div>

      <h3>Tus Archivos en la Nube (CU-02)</h3>
      <table style={{ width: "100%", borderCollapse: "collapse", border: "1px solid #444" }}>
        <thead>
          <tr style={{ backgroundColor: "#333" }}>
            <th style={{ padding: "10px", border: "1px solid #444" }}>Nombre</th>
            <th style={{ padding: "10px", border: "1px solid #444" }}>Tamaño</th>
            <th style={{ padding: "10px", border: "1px solid #444" }}>Hash SHA-256 (P-03)</th>
            <th style={{ padding: "10px", border: "1px solid #444" }}>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {files.map((f) => (
            <tr key={f.key}>
              <td style={{ padding: "10px", border: "1px solid #444" }}>{f.name}</td>
              <td style={{ padding: "10px", border: "1px solid #444" }}>{f.size} bytes</td>
              <td style={{ padding: "10px", border: "1px solid #444", fontSize: "0.8em", fontFamily: "monospace" }}>
                {f.hash || "No disponible"}
              </td>
              <td style={{ padding: "10px", border: "1px solid #444", textAlign: "center" }}>
                {/* CU-03: Abrir/Descargar [3] */}
                <a href={f.url} target="_blank" rel="noreferrer" style={{ color: "#2196f3", marginRight: "10px" }}>Abrir</a>
                <button onClick={() => handleDelete(f.key)} style={{ color: "#f44336", background: "none", border: "none", cursor: "pointer", textDecoration: "underline" }}>
                  Eliminar
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default App;