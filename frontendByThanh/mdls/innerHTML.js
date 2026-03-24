export default function InnerHTML(root, data, userName) {
    if (userName) {
        data.forEach(item => {
            const [time, status] = item;
            root.innerHTML += `<p>${time} - ${status}</p>
            `;
        });
    } else {
        Object.entries(data).forEach(([key, value]) => {
            console.log(key, value);
            if (key) {
                root.innerHTML += `<p>${key}</p>
                `;
            }
            value.forEach(item => {
                const [time, status] = item;
                root.innerHTML += `<p style="margin-left: 20px;">${time} - ${status}</p>
                `;
            });
        });
    }
}