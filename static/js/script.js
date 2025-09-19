// Custom JavaScript for HubSensi

// Initialize tooltips
document.addEventListener('DOMContentLoaded', function() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    })
    
    // Auto-dismiss alerts after 5 seconds
    var alerts = document.querySelectorAll('.alert:not(.alert-permanent)')
    alerts.forEach(function(alert) {
        setTimeout(function() {
            var bsAlert = new bootstrap.Alert(alert)
            bsAlert.close()
        }, 5000)
    })
    
    // QR Code scanning functionality
    if (typeof QRCode !== 'undefined') {
        initQRCodeScanner()
    }
})

// QR Code Scanner
function initQRCodeScanner() {
    const video = document.getElementById('qr-video')
    const resultContainer = document.getElementById('qr-result')
    
    if (!video) return
    
    const scanner = new QrScanner(
        video,
        result => {
            console.log('QR code detected:', result)
            scanner.stop()
            
            // Show result
            resultContainer.innerHTML = `
                <div class="alert alert-success">
                    <i class="bi bi-check-circle-fill"></i> 
                    QR Code terdeteksi: ${result}
                </div>
            `
            
            // Send to server
            fetch('/teacher/scan/process', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: new URLSearchParams({
                    'qr_data': result
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    resultContainer.innerHTML = `
                        <div class="alert alert-success">
                            <i class="bi bi-check-circle-fill"></i> 
                            ${data.message}
                            ${data.student_name ? `<br><strong>${data.student_name}</strong>` : ''}
                            ${data.status ? `<br>Status: ${data.status}` : ''}
                        </div>
                    `
                } else {
                    resultContainer.innerHTML = `
                        <div class="alert alert-danger">
                            <i class="bi bi-exclamation-circle-fill"></i> 
                            ${data.message}
                        </div>
                    `
                }
                
                // Restart scanner after 3 seconds
                setTimeout(() => {
                    resultContainer.innerHTML = ''
                    scanner.start()
                }, 3000)
            })
            .catch(error => {
                console.error('Error:', error)
                resultContainer.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="bi bi-exclamation-circle-fill"></i> 
                        Terjadi kesalahan: ${error.message}
                    </div>
                `
                
                // Restart scanner after 3 seconds
                setTimeout(() => {
                    resultContainer.innerHTML = ''
                    scanner.start()
                }, 3000)
            })
        },
        {
            highlightScanRegion: true,
            highlightCodeOutline: true,
        }
    )
    
    // Start scanner when page loads
    scanner.start()
    
    // Toggle scanner on button click
    const toggleBtn = document.getElementById('toggle-scanner')
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            if (scanner._active) {
                scanner.stop()
                toggleBtn.innerHTML = '<i class="bi bi-play-fill"></i> Mulai Scan'
            } else {
                scanner.start()
                toggleBtn.innerHTML = '<i class="bi bi-stop-fill"></i> Stop Scan'
            }
        })
    }
}

// Form validation
function validateForm(formId) {
    const form = document.getElementById(formId)
    if (!form) return true
    
    // Add Bootstrap validation classes
    const inputs = form.querySelectorAll('input, select, textarea')
    let isValid = true
    
    inputs.forEach(input => {
        if (input.hasAttribute('required') && !input.value) {
            input.classList.add('is-invalid')
            isValid = false
        } else {
            input.classList.remove('is-invalid')
        }
    })
    
    return isValid
}

// Datepicker initialization
function initDatepickers() {
    const dateInputs = document.querySelectorAll('input[type="date"]')
    dateInputs.forEach(input => {
        if (!input.value) {
            input.value = new Date().toISOString().split('T')[0]
        }
    })
}

// Export table to CSV
function exportTableToCSV(tableId, filename) {
    const table = document.getElementById(tableId)
    if (!table) return
    
    let csv = []
    const rows = table.querySelectorAll('tr')
    
    for (let i = 0; i < rows.length; i++) {
        let row = [], cols = rows[i].querySelectorAll('td, th')
        
        for (let j = 0; j < cols.length; j++) {
            // Clean text and add to row
            let text = cols[j].innerText.replace(/(\r\n|\n|\r)/gm, '').replace(/(\s\s)/gm, ' ')
            row.push('"' + text + '"')
        }
        
        csv.push(row.join(','))
    }
    
    // Download CSV file
    downloadCSV(csv.join('\n'), filename)
}

function downloadCSV(csv, filename) {
    const csvFile = new Blob([csv], { type: 'text/csv' })
    const downloadLink = document.createElement('a')
    
    // Create download link
    downloadLink.download = filename
    downloadLink.href = window.URL.createObjectURL(csvFile)
    downloadLink.style.display = 'none'
    
    document.body.appendChild(downloadLink)
    downloadLink.click()
    document.body.removeChild(downloadLink)
}

// Print element
function printElement(elementId) {
    const printContent = document.getElementById(elementId)
    if (!printContent) return
    
    const windowUrl = 'about:blank'
    const uniqueName = new Date()
    const windowName = 'Print' + uniqueName.getTime()
    const printWindow = window.open(windowUrl, windowName, 'left=50000,top=50000,width=0,height=0')
    
    printWindow.document.write(`
        <html>
            <head>
                <title>Print</title>
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
                <style>
                    body { padding: 20px; }
                    @media print {
                        .no-print { display: none !important; }
                    }
                </style>
            </head>
            <body>
                ${printContent.innerHTML}
                <script>
                    window.onload = function() {
                        window.print();
                        window.close();
                    }
                <\/script>
            </body>
        </html>
    `)
    
    printWindow.document.close()
}