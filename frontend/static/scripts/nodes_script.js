document.addEventListener('DOMContentLoaded', function() {
    const nodeRows = document.querySelectorAll('.node-row');
    const deleteBt = document.getElementById('delete-bt');

    const createForm = document.getElementById('node-creation-form');
    const createBt = document.getElementById('create-bt');
    createBt.disabled = false;

    nodeRows.forEach(row => {
        // Add click event to the entire row
        row.addEventListener('click', function(event) {
            // Find the radio button in this row
            const radioBtn = this.querySelector('.node-selector');
            
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
        // Find the selected node
        const selectedNode = document.querySelector('.node-selector:checked');
        
        if (selectedNode) {
            const nodeId = selectedNode.value;

            if (!confirm(`Are you sure you want to delete the node ${nodeId}?`)) {
                return;
            }
            
            // Delete the node
            fetch('/nodes_page', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    "action": "delete",
                    "node_data": {
                        "node_id": nodeId
                    }
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status == 'success') {
                    location.reload(true);
                }
                else {
                    alert(`Error. Status: ${data.status}, message: ${data.message}`);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Failed to delete the node');
            });
        }
    });

    createBt.addEventListener('click', function() {
        // Get data from form
        const formData = new FormData(createForm);
        const data = Object.fromEntries(formData.entries())

        // Send the query to create the node
        fetch('/nodes_page', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                "action": "create",
                "node_data": {
                    "node_id": data.node_id,
                    "profile": {
                        "position": data.node_position,
                        "token": data.node_token
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
                alert(`Error. Status: ${data.status}, message: ${data.message}`);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Failed to create the node');
        });
    });
});

