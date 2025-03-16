// دالة لجلب الـ Pages
function getPages() {
    const userAccessToken = document.getElementById('user_access_token').value;
    
    fetch('/get_page_tokens', {
        method: 'POST',
        body: new URLSearchParams({
            user_access_token: userAccessToken
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert(data.error);
        } else {
            let pageList = document.getElementById('pageList');
            pageList.innerHTML = '';
            data.forEach(page => {
                const pageOption = document.createElement('div');
                pageOption.innerHTML = `<input type="radio" name="page" value="${page.id}" /> ${page.name}`;
                pageList.appendChild(pageOption);
            });
        }
    })
    .catch(error => alert('Error fetching pages: ' + error));
}

// دالة للنشر على Facebook
function postToFacebook() {
    const pageId = document.querySelector('input[name="page"]:checked').value;
    const content = document.getElementById('content').value;
    const imagePath = document.getElementById('image_path').files[0] ? document.getElementById('image_path').files[0].name : '';
    const token = document.getElementById('user_access_token').value;

    fetch('/post_to_facebook', {
        method: 'POST',
        body: new URLSearchParams({
            page_id: pageId,
            content: content,
            image_path: imagePath,
            token: token
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.message) {
            alert(data.message);
        } else {
            alert(data.error);
        }
    })
    .catch(error => alert('Error posting: ' + error));
}
