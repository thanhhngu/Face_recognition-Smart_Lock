export default function WSSendFrame(ws, videoElement, qualityBlob, timeDelay) {
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    return setInterval(() => {
        if (!videoElement.videoWidth) return;
        canvas.width = videoElement.videoWidth;
        canvas.height = videoElement.videoHeight;
        ctx.drawImage(videoElement, 0, 0);
        canvas.toBlob(blob => {
            if (blob && ws.readyState === WebSocket.OPEN) {
                //arrayBuffer return promise
                blob.arrayBuffer().then(buffer => {
                    ws.send(buffer);
                });
            }
        }, "image/jpeg", qualityBlob);
    }, timeDelay)
}