document.addEventListener('DOMContentLoaded', function() {
    const userRows = document.querySelectorAll('.node-row');
    const deleteBt = document.getElementById('delete-bt');

    const createForm = document.getElementById('user-creation-form');
    const createBt = document.getElementById('create-bt');

    const readBadgeBt = document.getElementById('read-badge');

    userRows.forEach(row => {
        // Add click event to the entire row
        row.addEventListener('click', function(event) {
            // Find the radio button in this row
            const radioBtn = this.querySelector('.user-selector');
            
            if (radioBtn.checked) {
                // Prevent multiple selections if clicking on the radio button itself
                if (event.target !== radioBtn) {
                    radioBtn.checked = false;
                }

                // Update button state
                deleteBt.disabled = true;
            }
            else {
                // Prevent multiple selections if clicking on the radio button itself
                if (event.target !== radioBtn) {
                    radioBtn.checked = true;
                }

                // Update button state
                deleteBt.disabled = false;
            }
        });
    });

    deleteBt.addEventListener('click', function() {
        // Find the selected user
        const selectedUser = document.querySelector('.user-selector:checked');
        
        if (selectedUser) {
            const userId = selectedUser.value;

            if (!confirm(`Are you sure you want to delete the user ${userId}?`)) {
                return;
            }
            
            // Delete the user
            fetch('/users_page', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    "action": "delete",
                    "user_data": {
                        "user_id": userId
                    }
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status == 'success') {
                    location.reload(true);
                }
                else {
                    alert(`Error.\nStatus: ${data.status}\nMessage: ${data.message}`);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Failed to delete the user');
            });
        }
    });

    createBt.addEventListener('click', function() {
        // Get data from form
        const formData = new FormData(createForm);
        const data = Object.fromEntries(formData.entries())

        // Send the query to create the user
        fetch('/users_page', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                "action": "create",
                "user_data": {
                    "user_id": data.user_id,
                    "profile": {
                        "username": data.username,
                        "email": data.email,
                        "is_admin": data.is_admin == 'on',
                        "badge_expiration": data.badge_expiration
                    }
                }
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status == 'success') {
                location.reload(true);
            }
            else {
                alert(`Error.\nStatus: ${data.status}\nMessage: ${data.message}`);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Failed to create the user');
        });
    });

    readBadgeBt.addEventListener('click', function() {
        const uid_field = document.getElementById('uid-field');

        readNFC(uid_field);
    });
});


/**
 * Tries to read a mifare classic tag and write its UID into `uidField`.
 *
 * @param {HTMLElement} uidField - the text input for the UID
 */
async function readNFC(uidField) {
    if ('NDEFReader' in window) {
        try {
            const ndef = new NDEFReader();
            await ndef.scan();

            ndef.onreading = event => {
                const { message, serialNumber } = event;
                console.log('NFC tag detected:', serialNumber);
                
                uidField.value = serialNumber;
            };

            alert('Place your MIFARE Classic card near the NFC reader.');
        }
        catch (error) {
            console.error('Error:', error);
            alert('Error reading NFC tag. Please try again.');
        }
    }
    else {
        alert('Web NFC is not supported on this device.');
    }
}
