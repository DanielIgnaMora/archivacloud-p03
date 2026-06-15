import { useState, useEffect } from 'react';
import axios from 'axios';

function App() {
  const [file, setFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [status, setStatus] = useState("Esperando selección de archivo...");
  const [files, setFiles] = useState([]);

  // Parámetros Pareja P-03
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

  const handleFileChange = (e) => {
    // CORRECCIÓN: Volvemos a agregar el [0] para capturar el archivo individual
    const selectedFile = e.target.files[0];
    
    if (!selectedFile) {
      setFile(null);
      return;
    }

    // Validación de formato y tamaño para P-03
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

    // ¡ESTA LÍNEA ES LA QUE HABILITA EL BOTÓN!
    setFile(selectedFile);
    setStatus(`Archivo listo para subir: ${selectedFile.name}`);
  };

  const handleUpload = async () => {
    if (!file) return;
    setStatus("Solicitando permiso a S3...");
    setUploadProgress(0);

    // Evitamos strings vacíos en el Content-Type
    const cleanFileType = file.type && file.type.trim() !== "" ? file.type : "audio/mpeg";

    try {
      // CU-01: Obtener Presigned URL incluyendo los 3 parámetros de FastAPI (fileName, fileType, fileSize)
      const { data } = await axios.post("http://localhost:8000/api/upload/presigned-url", {
        fileName: file.name,
        fileType: cleanFileType,
        fileSize: file.size
      });

      // CU-01: Subida directa con barra de progreso
      await axios.put(data.presignedUrl, file, {
        headers: { "Content-Type": cleanFileType },
        onUploadProgress: (p) => setUploadProgress(Math.round((p.loaded * 100) / p.total))
      });

      setStatus("¡Subida exitosa!");
      setFile(null); // Limpiar selección tras éxito
      setUploadProgress(0);
      fetchFiles(); // Refrescar tabla (CU-02)
    } catch (error) {
      setStatus("Error en la subida. Verifica tus credenciales AWS.");
      console.error(error);
    }
  };

  const handleDelete = async (key) => {
    if (!window.confirm("¿Está seguro de eliminar este archivo?")) return;

    try {
      setStatus("Eliminando...");
      await axios.delete(`http://localhost:8000/api/files/${key}`);
      setStatus("Archivo eliminado.");
      fetchFiles(); // Refrescar tabla tras eliminar
    } catch (error) {
      setStatus("Error al eliminar el archivo.");
      console.error(error);
    }
  };

  return (
    <div style={{ padding: "40px", backgroundColor: "#121212", color: "white", minHeight: "100vh", fontFamily: "sans-serif" }}>
      <center>
        <h1>ArchivaCloud Portal - P-03</h1>
        <p>Región: <strong>{REGION}</strong> | Bucket: <strong>{BUCKET_NAME}</strong></p>
      </center>

      <div style={{ border: "1px solid #333", padding: "20px", margin: "20px 0", borderRadius: "10px", backgroundColor: "#1e1e1e" }}>
        <h3>Subir Audio (MP3/WAV - Máx 20MB)</h3>
        <input type="file" accept=".mp3,.wav" onChange={handleFileChange} />
        
        <button 
          onClick={handleUpload} 
          disabled={!file} 
          style={{ marginLeft: "10px", padding: "8px 20px", cursor: file ? "pointer" : "not-allowed" }}
        >
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
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ backgroundColor: "#333" }}>
            <th style={{ padding: "10px", border: "1px solid #444" }}>Nombre</th>
            <th style={{ padding: "10px", border: "1px solid #444" }}>Tamaño (bytes)</th>
            <th style={{ padding: "10px", border: "1px solid #444" }}>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {files.map((f) => (
            <tr key={f.key}>
              <td style={{ padding: "10px", border: "1px solid #444" }}>{f.name}</td>
              <td style={{ padding: "10px", border: "1px solid #444" }}>{f.size}</td>
              <td style={{ padding: "10px", border: "1px solid #444", textAlign: "center" }}>
                <a href={`https://${BUCKET_NAME}.s3.${REGION}.amazonaws.com/${f.key}`} target="_blank" rel="noreferrer" style={{ color: "#2196f3", marginRight: "10px" }}>Abrir</a>
                <button onClick={() => handleDelete(f.key)} style={{ color: "#f44336", background: "none", border: "none", cursor: "pointer", textDecoration: "underline" }}>Eliminar</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default App;