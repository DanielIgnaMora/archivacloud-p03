import { useState, useEffect } from 'react';
import axios from 'axios';

function App() {
  // Estados para la subida
  const [file, setFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [status, setStatus] = useState("");
  
  // Estado para el listado de archivos (CU-02)
  const [files, setFiles] = useState([]);

  // Parámetros obligatorios Pareja P-03
  const ALLOWED_TYPES = ["audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp3"];
  const MAX_SIZE = 20 * 1024 * 1024; // 20 MB [1]

  // Cargar lista de archivos al iniciar
  useEffect(() => {
    fetchFiles();
  }, []);

  const fetchFiles = async () => {
    try {
      const response = await axios.get("http://localhost:8000/api/files");
      setFiles(response.data);
    } catch (error) {
      console.error("Error al obtener archivos", error);
    }
  };

  const handleFileChange = (e) => {
    const selectedFile = e.target.files;
    if (!selectedFile) return;

    // CU-05: Validación de tipo (MP3/WAV) y tamaño (20MB) [1, 2]
    if (!ALLOWED_TYPES.includes(selectedFile.type)) {
      setStatus("Error: Solo se permiten archivos MP3 o WAV.");
      setFile(null);
      return;
    }

    if (selectedFile.size > MAX_SIZE) {
      setStatus("Error: El archivo excede el límite de 20 MB.");
      setFile(null);
      return;
    }

    setFile(selectedFile);
    setStatus("Archivo validado y listo.");
  };

  const handleUpload = async () => {
    if (!file) return;
    setStatus("Solicitando permiso de subida...");
    setUploadProgress(0);

    try {
      // PASO 1: Obtener Presigned URL del Backend [3]
      const { data } = await axios.post("http://localhost:8000/api/upload/presigned-url", {
        fileName: file.name,
        fileType: file.type,
        fileSize: file.size
      });

      // PASO 2: Subida directa a S3 con barra de progreso (CU-01) [2, 4]
      setStatus("Subiendo directamente a Amazon S3...");
      await axios.put(data.presignedUrl, file, {
        headers: { "Content-Type": file.type },
        onUploadProgress: (progressEvent) => {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress(percent);
        }
      });

      setStatus("¡Archivo subido con éxito!");
      setFile(null);
      fetchFiles(); // Refrescar lista (CU-02) [2]
    } catch (error) {
      // SEC-07: Error sin trazas técnicas [5]
      setStatus("Error en la comunicación con el servicio.");
    }
  };

  const handleDelete = async (key) => {
    // CU-04: Eliminación con confirmación [2]
    if (!window.confirm("¿Estás seguro de eliminar este archivo? Esta acción es irreversible.")) return;

    try {
      await axios.delete(`http://localhost:8000/api/files/${key}`);
      setStatus("Archivo eliminado.");
      fetchFiles();
    } catch (error) {
      setStatus("No se pudo eliminar el archivo.");
    }
  };

  return (
    <div style={{ padding: "40px", fontFamily: "sans-serif" }}>
      <h1>ArchivaCloud Portal - P-03</h1>
      <p>Región: <strong>us-west-2</strong> | Bucket: <strong>archivacloud-p03dm</strong></p>

      {/* Sección de Carga */}
      <div style={{ marginBottom: "30px", border: "1px solid #ccc", padding: "20px" }}>
        <h3>Subir Nuevo Audio (MP3/WAV - Máx 20MB)</h3>
        <input type="file" accept=".mp3,.wav" onChange={handleFileChange} />
        <button onClick={handleUpload} disabled={!file} style={{ marginLeft: "10px" }}>
          Subir a S3
        </button>

        {/* Barra de progreso visible (CU-01) */}
        {uploadProgress > 0 && (
          <div style={{ width: "100%", backgroundColor: "#eee", marginTop: "15px" }}>
            <div style={{ 
              width: `${uploadProgress}%`, 
              height: "25px", 
              backgroundColor: "#2196F3", 
              color: "white", 
              textAlign: "center" 
            }}>
              {uploadProgress}%
            </div>
          </div>
        )}
        <p>Status: {status}</p>
      </div>

      {/* Sección de Listado (CU-02) */}
      <h3>Tus Archivos en la Nube</h3>
      <table border="1" cellPadding="10" style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th>Nombre</th>
            <th>Tamaño (bytes)</th>
            <th>Última Modificación</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {files.map((f) => (
            <tr key={f.key}>
              <td>{f.name}</td>
              <td>{f.size}</td>
              <td>{new Date(f.lastModified).toLocaleString()}</td>
              <td>
                {/* CU-03 y CU-04 [2] */}
                <a href={`https://archivacloud-p03dm.s3.us-west-2.amazonaws.com/${f.key}`} target="_blank" rel="noreferrer">
                  Abrir
                </a>
                {" | "}
                <button onClick={() => handleDelete(f.key)} style={{ color: "red", cursor: "pointer" }}>
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