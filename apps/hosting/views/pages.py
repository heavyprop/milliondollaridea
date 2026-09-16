from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.cache import never_cache


@login_required(login_url="/accounts/")
@never_cache
def help_page(request):
    return render(
        request,
        "hosting/help.html",
        {
            "publish_blocks": [
                {
                    "kind": "code",
                    "language": "Terminal",
                    "text": "safe publish ./my-project",
                }
            ],
            "download_blocks": [
                {
                    "kind": "code",
                    "language": "Terminal",
                    "text": "safe get username/project-name ./downloaded-project",
                }
            ],
        },
    )
