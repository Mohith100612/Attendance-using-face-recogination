import { useRef, useState } from 'react'
import Webcam from 'react-webcam'

export default function RegisterPage() {
  const webcamRef = useRef(null)

  const [form, setForm] = useState({ name: '', email: '', phone: '', linkedin: '', occupation: '' })
  const [tab, setTab] = useState('upload')
  const [preview, setPreview] = useState(null)
  const [uploadFile, setUploadFile] = useState(null)
  const [captured, setCaptured] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [status, setStatus] = useState(null) // null | 'success' | 'error'
  const [statusMsg, setStatusMsg] = useState('')

  function handleField(e) {
    setForm(f => ({ ...f, [e.target.name]: e.target.value }))
  }

  function handleFileChange(e) {
    const file = e.target.files[0]
    if (!file) return
    setUploadFile(file)
    setPreview(URL.createObjectURL(file))
    setCaptured(null)
  }

  function handleCapture() {
    const img = webcamRef.current?.getScreenshot()
    if (!img) return
    setCaptured(img)
    setPreview(img)
    setUploadFile(null)
  }

  function switchTab(t) {
    setTab(t)
    setPreview(null)
    setUploadFile(null)
    setCaptured(null)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.name.trim()) return showStatus('error', 'Full name is required.')
    if (!form.email.trim()) return showStatus('error', 'Email is required.')
    if (!uploadFile && !captured) return showStatus('error', 'Please provide a face photo.')

    setSubmitting(true)
    setStatus(null)

    const fd = new FormData()
    Object.entries(form).forEach(([k, v]) => fd.append(k, v.trim()))
    if (uploadFile) fd.append('image', uploadFile)
    else fd.append('image_base64', captured)

    try {
      const res = await fetch('/api/register', { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) {
        showStatus('error', data.detail || 'Registration failed.')
      } else {
        showStatus('success', `${data.name} has been registered successfully!`)
        setForm({ name: '', email: '', phone: '', linkedin: '', occupation: '' })
        setPreview(null)
        setUploadFile(null)
        setCaptured(null)
      }
    } catch {
      showStatus('error', 'Network error. Make sure the backend is running.')
    } finally {
      setSubmitting(false)
    }
  }

  function showStatus(type, msg) {
    setStatus(type)
    setStatusMsg(msg)
  }

  return (
    <div className="sr-page">
      <div className="sr-card">

        <div className="sr-header">
          <h1 className="sr-title">Spotregister</h1>
          <p className="sr-sub">Fill in the details and capture your face to register for the event.</p>
        </div>

        <form onSubmit={handleSubmit} className="sr-form">

          {/* Row 1: Name + Email */}
          <div className="sr-row">
            <div className="sr-field">
              <label>Full Name <span className="req">*</span></label>
              <input name="name" placeholder="John Doe" value={form.name}
                onChange={handleField} disabled={submitting} />
            </div>
            <div className="sr-field">
              <label>Email Address <span className="req">*</span></label>
              <input name="email" type="email" placeholder="john@example.com" value={form.email}
                onChange={handleField} disabled={submitting} />
            </div>
          </div>

          {/* Row 2: Phone + Occupation */}
          <div className="sr-row">
            <div className="sr-field">
              <label>Phone Number</label>
              <input name="phone" placeholder="+91 98765 43210" value={form.phone}
                onChange={handleField} disabled={submitting} />
            </div>
            <div className="sr-field">
              <label>Occupation</label>
              <input name="occupation" placeholder="Software Engineer" value={form.occupation}
                onChange={handleField} disabled={submitting} />
            </div>
          </div>

          {/* LinkedIn full width */}
          <div className="sr-field">
            <label>LinkedIn Profile URL</label>
            <input name="linkedin" placeholder="https://linkedin.com/in/yourprofile"
              value={form.linkedin} onChange={handleField} disabled={submitting} />
          </div>

          {/* Face photo */}
          <div className="sr-photo-section">
            <label>Face Photo <span className="req">*</span></label>
            <div className="sr-tabs">
              <button type="button" className={tab === 'upload' ? 'active' : ''} onClick={() => switchTab('upload')}>
                Upload Photo
              </button>
              <button type="button" className={tab === 'camera' ? 'active' : ''} onClick={() => switchTab('camera')}>
                Use Camera
              </button>
            </div>

            <div className="sr-photo-area">
              {tab === 'upload' && (
                <>
                  <input type="file" accept="image/*" id="sr-file" className="sr-hidden"
                    onChange={handleFileChange} disabled={submitting} />
                  {!preview ? (
                    <label htmlFor="sr-file" className="sr-drop">
                      <div className="sr-drop-icon">+</div>
                      <span>Click to upload a photo</span>
                      <span className="sr-drop-hint">JPG, PNG — clear front-facing face</span>
                    </label>
                  ) : (
                    <div className="sr-preview-wrap">
                      <img src={preview} alt="preview" className="sr-preview" />
                      <label htmlFor="sr-file" className="sr-retake">Change Photo</label>
                    </div>
                  )}
                </>
              )}

              {tab === 'camera' && (
                <>
                  {!captured ? (
                    <div className="sr-cam-wrap">
                      <Webcam ref={webcamRef} audio={false} screenshotFormat="image/jpeg"
                        screenshotQuality={0.9}
                        videoConstraints={{ width: 400, height: 300, facingMode: 'user' }}
                        className="sr-cam" />
                      <button type="button" className="sr-capture-btn" onClick={handleCapture}>
                        Capture
                      </button>
                    </div>
                  ) : (
                    <div className="sr-preview-wrap">
                      <img src={preview} alt="captured" className="sr-preview" />
                      <button type="button" className="sr-retake"
                        onClick={() => { setCaptured(null); setPreview(null) }}>
                        Retake
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>

          {/* Status message */}
          {status && (
            <div className={`sr-status ${status}`}>{statusMsg}</div>
          )}

          <button type="submit" className="sr-submit" disabled={submitting}>
            {submitting ? 'Registering...' : 'Register'}
          </button>

        </form>
      </div>
    </div>
  )
}
