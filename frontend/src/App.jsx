import { useState, useEffect } from 'react';
import axios from 'axios';

function App() {
  const [file, setFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [status, setStatus] = useState("Esperando selección de archivo...");
  const [files, setFiles] = useState([]);

  const BUCKET_NAME = "archivacloud-p03dm";
  const REGION = "us-west-2";
  const MAX_SIZE = 20 * 1024 * 1024; // 20 MB

  useEffect(() => {
    fetchFiles();
  }, []);

  const fetchFiles = async () => {
    try {
      const response = await axios.get("http://localhost:8000/api/files");
      setFiles(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      console.error("Error al listar archivos:", error);
      setStatus("Error al conectar con el backend.");
    }
  };

  const calculateHash = async (fileToHash) => {
    const buffer = await fileToHash.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  };

  const handleFileChange = (e) => {
    if (!e.target.files || e.target.files.length === 0) return;

    const selectedFile = e.target.files[0];

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

  const handleUpload = async () => {
    if (!file) return;

    try {
      setStatus("Calculando integridad (SHA-256)...");
      const fileHash = await calculateHash(file);

      setStatus("Solicitando permiso a S3...");
      setUploadProgress(0);

      // ✅ FIX 422: ahora mandamos fileSize
      const { data } = await axios.post("http://localhost:8000/api/upload/presigned-url", {
        fileName: file.name,
        fileType: file.type || "audio/mpeg",
        fileSize: file.size, // 👈 clave
        fileHash: fileHash
      });

      await axios.put(data.presignedUrl, file, {
        headers: { "Content-Type": file.type || "audio/mpeg",
          "x-amz-meta-sha256": fileHash
         },
        onUploadProgress: (p) =>
          setUploadProgress(Math.round((p.loaded * 100) / p.total))
      });

      setStatus("¡Subida exitosa e integridad verificada!");
      setFile(null);
      setUploadProgress(0);
      fetchFiles();
    } catch (error) {
      console.error("Detalle error:", error.response?.data || error.message);
      setStatus("Error en el proceso de subida.");
    }
  };

  const handleDelete = async (key) => {
    if (!window.confirm("¿Está seguro de eliminar este archivo?")) return;

    try {
      setStatus("Eliminando archivo...");
      await axios.delete(`http://localhost:8000/api/files/${key}`);
      setStatus("Archivo eliminado exitosamente.");
      fetchFiles();
    } catch (error) {
      setStatus("Error al eliminar.");
    }
  };

  return (
    <div style={{ padding: "40px", backgroundColor: "#121212", color: "white", minHeight: "100vh", fontFamily: "sans-serif" }}>
      <center>
        <h1>ArchivaCloud Portal - P-03</h1>
        <p>Región: <strong>{REGION}</strong> | Bucket: <strong>{BUCKET_NAME}</strong></p>
      </center>

      <div style={{ border: "1px solid #333", padding: "20px", margin: "20px 0", borderRadius: "10px", backgroundColor: "#1e1e1e" }}>
        <h3>Subir Audio</h3>

        <input type="file" accept=".mp3,.wav" onChange={handleFileChange} />

        <button onClick={handleUpload} disabled={!file} style={{ marginLeft: "10px", padding: "8px 20px" }}>
          Subir
        </button>

        {uploadProgress > 0 && (
          <div style={{ width: "100%", backgroundColor: "#444", marginTop: "15px" }}>
            <div style={{ width: `${uploadProgress}%`, height: "20px", backgroundColor: "#4caf50" }}>
              {uploadProgress}%
            </div>
          </div>
        )}

        <p><strong>Status:</strong> {status}</p>
      </div>

      <h3>Archivos</h3>

      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th>Nombre</th>
            <th>Tamaño</th>
            <th>Hash</th>
            <th>Acciones</th>
          </tr>
        </thead>

        <tbody>
          {files.map((f) => (
            <tr key={f.key}>
              <td>{f.name}</td>
              <td>{f.size}</td>
              <td>{f.hash}</td>
              <td>
                <a href={f.url} target="_blank" rel="noreferrer">Abrir</a>
                <button onClick={() => handleDelete(f.key)}>Eliminar</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default App;