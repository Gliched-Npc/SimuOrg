import { useState } from 'react';
import Navbar from '../components/Navbar';

function UploadData() {
    const [file, setFile] = useState(null);
    const [status, setStatus] = useState('');

    const handleUpload = async (e) => {
        e.preventDefault();
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);

        try {
            setStatus('Uploading...');
            const res = await fetch('http://localhost:8000/api/upload', {
                method: 'POST',
                body: formData,
            });

            if (res.ok) {
                setStatus('Upload successful!');
            } else {
                setStatus('Upload failed. Please try again.');
            }
        } catch (err) {
            setStatus('Error connecting to the server.');
        }
    };

    return (
        <div className="upload-page">
            <Navbar />
            <h1>Upload Dataset</h1>
            <form onSubmit={handleUpload}>
                <input
                    type="file"
                    accept=".csv"
                    onChange={(e) => setFile(e.target.files[0])}
                />
                <button type="submit" disabled={!file}>
                    Upload CSV
                </button>
            </form>
            {status && <p className="upload-status">{status}</p>}
        </div>
    );
}

export default UploadData;
