document.addEventListener('DOMContentLoaded', function() {
    const freeNodeRows = document.querySelectorAll('.free-node-row');
    const reservedNodeRows = document.querySelectorAll('.reserved-node-row');
    const reserveBt = document.getElementById('reserve-bt');
    const cancelBt = document.getElementById('cancel-bt');

    freeNodeRows.forEach(row => {
        // Add click event to the entire row
        row.addEventListener('click', function(event) {
            // Find the radio button in this row
            const radioBtn = this.querySelector('.free-node-selector');
            
            if (radioBtn.checked) {
                // Prevent multiple selections if clicking on the radio button itself
                if (event.target !== radioBtn) {
                    radioBtn.checked = false;
                }

                // Update button state
                reserveBt.disabled = true;
            }
            else {
                // Prevent multiple selections if clicking on the radio button itself
                if (event.target !== radioBtn) {
                    radioBtn.checked = true;
                }

                // Update button state
                reserveBt.disabled = false;
            }
        });
    });

    reserveBt.addEventListener('click', function() {
        // Find the selected node
        const selectedNode = document.querySelector('.free-node-selector:checked');
        
        if (selectedNode) {
            const nodeId = selectedNode.value;
            
            // Reserve the node
            fetch('/reservation_page', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    "action": "reserve",
                    "node_id": nodeId
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status == 'success') {
                    // alert(`Node ${nodeId} reserved successfully.`);
                    location.reload(true);
                }
                else if (data.status == 'reservation_error') {
                    alert('Error while reserving node.\nNote that you can only reserve one node max.\nPlease refresh and retry otherwise.');
                }
                else {
                    alert(`Error.\nStatus: ${data.status}\nMessage: ${data.message}`);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Failed to reserve the node');
            });
        }
    });

    reservedNodeRows.forEach(row => {
        // Add click event to the entire row
        row.addEventListener('click', function(event) {
            // Find the radio button in this row
            const radioBtn = this.querySelector('.reserved-node-selector');
            
            if (radioBtn.checked) {
                // Prevent multiple selections if clicking on the radio button itself
                if (event.target !== radioBtn) {
                    radioBtn.checked = false;
                }

                // Update button state
                cancelBt.disabled = true;
            }
            else {
                // Prevent multiple selections if clicking on the radio button itself
                if (event.target !== radioBtn) {
                    radioBtn.checked = true;
                }

                // Update button state
                cancelBt.disabled = false;
            }
        });
    });

    cancelBt.addEventListener('click', function() {
        // Find the selected node
        const selectedNode = document.querySelector('.reserved-node-selector:checked');
        
        if (selectedNode) {
            const nodeId = selectedNode.value;
            
            // Reserve the node
            fetch('/reservation_page', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    "action": "cancel",
                    "node_id": nodeId
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status == 'success') {
                    // alert('Successfully cancelled reservation');
                    location.reload(true);
                }
                else if (data.status == 'reservation_error') {
                    alert('Error while canceling reservation. Please retry (and refresh page)');
                }
                else {
                    alert(`Error.\nStatus: ${data.status}\nMessage: ${data.message}`);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Failed to reserve the node');
            });
        }
    });
});
