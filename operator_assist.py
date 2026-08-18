import importlib.util
import json
import re
from pathlib import Path


WRAPPER_VERSION = "2026-07-14-it-mode1"
CURRENT_DIR = Path(__file__).resolve().parent
BASE_SCRIPT_CANDIDATES = [
    CURRENT_DIR / "operator_assist_chat_bridge_v5_base.py",
    Path("D:/OPERATOR_ASIST/operator_assist_chat_bridge_v5_base.py"),
]


def load_base_module():
    for candidate in BASE_SCRIPT_CANDIDATES:
        if not candidate.exists():
            continue

        spec = importlib.util.spec_from_file_location("operator_assist_chat5_base_module", candidate)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, candidate

    raise FileNotFoundError("Base Chat Bridge v5 script was not found.")


_base_mod, _base_path = load_base_module()
_runtime = _base_mod._base_mod._base
_runtime.LOGGER.info("Loaded top wrapper. base_source=%s wrapper_version=%s", _base_path, WRAPPER_VERSION)

IT_MODE_REPLACEMENTS = {
    ".net": ".NET",
    "active directory": "Active Directory",
    "amazon ec2": "Amazon EC2",
    "amazon rds": "Amazon RDS",
    "amazon s3": "Amazon S3",
    "angular": "Angular",
    "ansible": "Ansible",
    "apache": "Apache",
    "api": "API",
    "asp net": "ASP.NET",
    "asp.net": "ASP.NET",
    "aws": "AWS",
    "aws lambda": "AWS Lambda",
    "azure": "Azure",
    "babel": "Babel",
    "bash": "Bash",
    "bios": "BIOS",
    "bit bucket": "Bitbucket",
    "bitbucket": "Bitbucket",
    "bootstrap": "Bootstrap",
    "c plus plus": "C++",
    "c sharp": "C#",
    "c#": "C#",
    "c++": "C++",
    "cassandra": "Cassandra",
    "cdn": "CDN",
    "centos": "CentOS",
    "ci cd": "CI/CD",
    "cicd": "CI/CD",
    "circle ci": "CircleCI",
    "circleci": "CircleCI",
    "cli": "CLI",
    "click house": "ClickHouse",
    "clickhouse": "ClickHouse",
    "cloud flare": "Cloudflare",
    "cloudflare": "Cloudflare",
    "confluence": "Confluence",
    "cpp": "C++",
    "cpu": "CPU",
    "crm": "CRM",
    "css": "CSS",
    "csv": "CSV",
    "cuda": "CUDA",
    "dart": "Dart",
    "debian": "Debian",
    "devops": "DevOps",
    "dhcp": "DHCP",
    "django": "Django",
    "dns": "DNS",
    "docker": "Docker",
    "docker compose": "Docker Compose",
    "dot net": ".NET",
    "dotnet": ".NET",
    "dynamo db": "DynamoDB",
    "dynamodb": "DynamoDB",
    "ec2": "Amazon EC2",
    "elastic search": "Elasticsearch",
    "elasticsearch": "Elasticsearch",
    "entity framework": "Entity Framework",
    "erp": "ERP",
    "eslint": "ESLint",
    "etl": "ETL",
    "express js": "Express.js",
    "express.js": "Express.js",
    "fast api": "FastAPI",
    "fastapi": "FastAPI",
    "firebase": "Firebase",
    "flask": "Flask",
    "gcp": "GCP",
    "git": "Git",
    "git hub": "GitHub",
    "git lab": "GitLab",
    "github": "GitHub",
    "gitlab": "GitLab",
    "gitops": "GitOps",
    "go lang": "Go",
    "golang": "Go",
    "gpu": "GPU",
    "grafana": "Grafana",
    "graphql": "GraphQL",
    "grpc": "gRPC",
    "gui": "GUI",
    "hdd": "HDD",
    "helm": "Helm",
    "hibernate": "Hibernate",
    "html": "HTML",
    "http": "HTTP",
    "https": "HTTPS",
    "ide": "IDE",
    "iis": "IIS",
    "imap": "IMAP",
    "ip": "IP",
    "ipv4": "IPv4",
    "ipv6": "IPv6",
    "java": "Java",
    "java script": "JavaScript",
    "javascript": "JavaScript",
    "jenkins": "Jenkins",
    "jira": "Jira",
    "jquery": "jQuery",
    "json": "JSON",
    "jupyter": "Jupyter",
    "jwt": "JWT",
    "k8s": "Kubernetes",
    "kafka": "Kafka",
    "kibana": "Kibana",
    "kotlin": "Kotlin",
    "kubernetes": "Kubernetes",
    "lambda": "AWS Lambda",
    "laravel": "Laravel",
    "ldap": "LDAP",
    "less": "Less",
    "linux": "Linux",
    "load balancer": "Load Balancer",
    "logstash": "Logstash",
    "maria db": "MariaDB",
    "mariadb": "MariaDB",
    "material ui": "Material UI",
    "microservices": "Microservices",
    "mobx": "MobX",
    "mongo db": "MongoDB",
    "mongodb": "MongoDB",
    "monolith": "Monolith",
    "ms sql server": "MS SQL Server",
    "mssql": "MS SQL Server",
    "my sql": "MySQL",
    "mysql": "MySQL",
    "nas": "NAS",
    "nat": "NAT",
    "nest js": "NestJS",
    "nestjs": "NestJS",
    "netlify": "Netlify",
    "next js": "Next.js",
    "next.js": "Next.js",
    "nginx": "Nginx",
    "no sql": "NoSQL",
    "node js": "Node.js",
    "node.js": "Node.js",
    "nosql": "NoSQL",
    "numpy": "NumPy",
    "nuxt js": "Nuxt.js",
    "nuxt.js": "Nuxt.js",
    "oauth": "OAuth",
    "opencv": "OpenCV",
    "openid connect": "OpenID Connect",
    "oracle database": "Oracle Database",
    "oracle db": "Oracle Database",
    "orm": "ORM",
    "pandas": "Pandas",
    "php": "PHP",
    "pop3": "POP3",
    "postgres": "PostgreSQL",
    "postgres sql": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "power shell": "PowerShell",
    "powershell": "PowerShell",
    "prettier": "Prettier",
    "prometheus": "Prometheus",
    "proxmox": "Proxmox",
    "py torch": "PyTorch",
    "python": "Python",
    "pytorch": "PyTorch",
    "qa": "QA",
    "rabbit mq": "RabbitMQ",
    "rabbitmq": "RabbitMQ",
    "raid": "RAID",
    "ram": "RAM",
    "rds": "Amazon RDS",
    "react": "React",
    "redis": "Redis",
    "redux": "Redux",
    "regex": "Regex",
    "regexp": "Regex",
    "rest api": "REST API",
    "restful": "RESTful",
    "reverse proxy": "Reverse Proxy",
    "ruby": "Ruby",
    "rust": "Rust",
    "s3": "Amazon S3",
    "saml": "SAML",
    "san": "SAN",
    "sass": "Sass",
    "scikit learn": "scikit-learn",
    "scikit-learn": "scikit-learn",
    "scss": "SCSS",
    "sdk": "SDK",
    "sentry": "Sentry",
    "smtp": "SMTP",
    "spring": "Spring",
    "spring boot": "Spring Boot",
    "sql": "SQL",
    "sql lite": "SQLite",
    "sqlite": "SQLite",
    "ssd": "SSD",
    "ssh": "SSH",
    "ssl": "SSL",
    "sso": "SSO",
    "story book": "Storybook",
    "storybook": "Storybook",
    "svelte": "Svelte",
    "swift": "Swift",
    "symfony": "Symfony",
    "tailwind": "Tailwind CSS",
    "tailwind css": "Tailwind CSS",
    "tcp": "TCP",
    "team city": "TeamCity",
    "teamcity": "TeamCity",
    "tensor flow": "TensorFlow",
    "tensorflow": "TensorFlow",
    "terraform": "Terraform",
    "tls": "TLS",
    "travis ci": "Travis CI",
    "type script": "TypeScript",
    "typescript": "TypeScript",
    "ubuntu": "Ubuntu",
    "udp": "UDP",
    "uefi": "UEFI",
    "uri": "URI",
    "url": "URL",
    "vercel": "Vercel",
    "vite": "Vite",
    "vlan": "VLAN",
    "vmware": "VMware",
    "vpn": "VPN",
    "vue js": "Vue.js",
    "vue.js": "Vue.js",
    "webhook": "Webhook",
    "webpack": "Webpack",
    "websocket": "WebSocket",
    "windows server": "Windows Server",
    "xml": "XML",
    "yaml": "YAML",
    "yandex cloud": "Yandex Cloud",
    "yii2": "Yii2",
    "\u0430\u0432\u044d\u0441": "AWS",
    "\u0430\u0436\u0443\u0440": "Azure",
    "\u0430\u0439 \u0430\u0439 \u044d\u0441": "IIS",
    "\u0430\u0439 \u0434\u0438 \u0438": "IDE",
    "\u0430\u0439 \u043c\u0430\u043f": "IMAP",
    "\u0430\u0439 \u043f\u0438": "IP",
    "\u0430\u0439 \u043f\u0438 \u0432\u0438 \u0441\u0438\u043a\u0441": "IPv6",
    "\u0430\u0439 \u043f\u0438 \u0432\u0438 \u0444\u043e": "IPv4",
    "\u0430\u0439\u0430\u0439\u044d\u0441": "IIS",
    "\u0430\u0439\u0434\u0438\u0438": "IDE",
    "\u0430\u0439\u0434\u0438\u044f": "IDE",
    "\u0430\u0439\u043c\u0430\u043f": "IMAP",
    "\u0430\u0439\u043f\u0438": "IP",
    "\u0430\u0439\u043f\u0438\u0432\u0438\u0444\u043e": "IPv4",
    "\u0430\u043a\u0442\u0438\u0432 \u0434\u0438\u0440\u0435\u043a\u0442\u043e\u0440\u0438": "Active Directory",
    "\u0430\u043a\u0442\u0438\u0432\u0434\u0438\u0440\u0435\u043a\u0442\u043e\u0440\u0438": "Active Directory",
    "\u0430\u043c\u0430\u0437\u043e\u043d \u0430\u0440 \u0434\u0438 \u044d\u0441": "Amazon RDS",
    "\u0430\u043c\u0430\u0437\u043e\u043d \u0438 \u0441\u0438 \u0434\u0432\u0430": "Amazon EC2",
    "\u0430\u043c\u0430\u0437\u043e\u043d \u044d\u0441 \u0442\u0440\u0438": "Amazon S3",
    "\u0430\u043d\u0433\u0443\u043b\u044f\u0440": "Angular",
    "\u0430\u043d\u0441\u0438\u0431\u043b": "Ansible",
    "\u0430\u043f\u0430\u0447": "Apache",
    "\u0430\u043f\u0430\u0447\u0438": "Apache",
    "\u0430\u043f\u0438": "API",
    "\u0430\u0440 \u0434\u0438 \u044d\u0441": "Amazon RDS",
    "\u0430\u0441\u043f \u043d\u0435\u0442": "ASP.NET",
    "\u0430\u0441\u043f\u043d\u0435\u0442": "ASP.NET",
    "\u0430\u0448 \u0442\u0438 \u0442\u0438 \u043f\u0438": "HTTP",
    "\u0430\u0448 \u0442\u0438 \u0442\u0438 \u043f\u0438 \u044d\u0441": "HTTPS",
    "\u0430\u0448 \u0442\u0438 \u044d\u043c \u044d\u043b": "HTML",
    "\u0431\u0430\u0431\u0435\u043b": "Babel",
    "\u0431\u0430\u0439\u043e\u0441": "BIOS",
    "\u0431\u0430\u0448": "Bash",
    "\u0431\u0435\u0439\u0431\u0435\u043b": "Babel",
    "\u0431\u0438\u0442 \u0431\u0430\u043a\u0435\u0442": "Bitbucket",
    "\u0431\u0438\u0442\u0431\u0430\u043a\u0435\u0442": "Bitbucket",
    "\u0431\u0443\u0442\u0441\u0442\u0440\u0430\u043f": "Bootstrap",
    "\u0432\u0430\u0439\u0442": "Vite",
    "\u0432\u0435\u0431 \u0441\u043e\u043a\u0435\u0442": "WebSocket",
    "\u0432\u0435\u0431 \u0445\u0443\u043a": "Webhook",
    "\u0432\u0435\u0431\u043f\u0430\u043a": "Webpack",
    "\u0432\u0435\u0431\u0441\u043e\u043a\u0435\u0442": "WebSocket",
    "\u0432\u0435\u0431\u0445\u0443\u043a": "Webhook",
    "\u0432\u0435\u0440\u0441\u0435\u043b": "Vercel",
    "\u0432\u0438 \u043b\u0430\u043d": "VLAN",
    "\u0432\u0438 \u043f\u0438 \u044d\u043d": "VPN",
    "\u0432\u0438 \u044d\u043c \u0432\u0435\u0440": "VMware",
    "\u0432\u0438\u043b\u0430\u043d": "VLAN",
    "\u0432\u0438\u043d\u0434\u043e\u0432\u0441 \u0441\u0435\u0440\u0432\u0435\u0440": "Windows Server",
    "\u0432\u0438\u043d\u0434\u043e\u0443\u0441 \u0441\u0435\u0440\u0432\u0435\u0440": "Windows Server",
    "\u0432\u0438\u0442": "Vite",
    "\u0432\u0438\u044d\u043c\u0432\u0435\u0440": "VMware",
    "\u0432\u043b\u0430\u043d": "VLAN",
    "\u0432\u043f\u043d": "VPN",
    "\u0432\u044c\u044e": "Vue.js",
    "\u0432\u044c\u044e \u0434\u0436\u0435\u0439\u0441": "Vue.js",
    "\u0432\u044c\u044e \u0434\u0436\u0438 \u044d\u0441": "Vue.js",
    "\u0432\u044d\u0431\u043f\u0430\u043a": "Webpack",
    "\u0432\u044d\u0431\u0441\u043e\u043a\u0435\u0442": "WebSocket",
    "\u0432\u044d\u0431\u0445\u0443\u043a": "Webhook",
    "\u0433\u0438\u0442": "Git",
    "\u0433\u0438\u0442 \u043b\u0430\u0431": "GitLab",
    "\u0433\u0438\u0442 \u043e\u043f\u0441": "GitOps",
    "\u0433\u0438\u0442 \u0445\u0430\u0431": "GitHub",
    "\u0433\u0438\u0442\u043b\u0430\u0431": "GitLab",
    "\u0433\u0438\u0442\u043e\u043f\u0441": "GitOps",
    "\u0433\u0438\u0442\u0445\u0430\u0431": "GitHub",
    "\u0433\u043e": "Go",
    "\u0433\u043e\u043b\u044d\u043d\u0433": "Go",
    "\u0433\u043f\u0443": "GPU",
    "\u0433\u0440\u0430\u0444 \u043a\u0443 \u044d\u043b": "GraphQL",
    "\u0433\u0440\u0430\u0444 \u043a\u044c\u044e \u044d\u043b": "GraphQL",
    "\u0433\u0440\u0430\u0444\u0430\u043d\u0430": "Grafana",
    "\u0433\u0440\u0430\u0444\u043a\u044c\u044e\u044d\u043b": "GraphQL",
    "\u0433\u0443\u0438": "GUI",
    "\u0434\u0430\u0439\u043d\u0430\u043c\u043e\u0434\u0431": "DynamoDB",
    "\u0434\u0430\u0440\u0442": "Dart",
    "\u0434\u0435\u0431\u0438\u0430\u043d": "Debian",
    "\u0434\u0435\u0432 \u043e\u043f\u0441": "DevOps",
    "\u0434\u0435\u0432\u043e\u043f\u0441": "DevOps",
    "\u0434\u0436\u0430\u0432\u0430": "Java",
    "\u0434\u0436\u0430\u0432\u0430 \u0441\u043a\u0440\u0438\u043f\u0442": "JavaScript",
    "\u0434\u0436\u0430\u0432\u0430\u0441\u043a\u0440\u0438\u043f\u0442": "JavaScript",
    "\u0434\u0436\u0430\u043d\u0433\u043e": "Django",
    "\u0434\u0436\u0435\u0439 \u0434\u0430\u0431\u043b\u044e \u0442\u0438": "JWT",
    "\u0434\u0436\u0435\u0439 \u043a\u0432\u0435\u0440\u0438": "jQuery",
    "\u0434\u0436\u0435\u0439 \u0441\u043e\u043d": "JSON",
    "\u0434\u0436\u0435\u0439\u0432\u0438\u0442\u0438": "JWT",
    "\u0434\u0436\u0435\u0439\u043a\u0432\u0435\u0440\u0438": "jQuery",
    "\u0434\u0436\u0435\u0439\u0441\u043e\u043d": "JSON",
    "\u0434\u0436\u0435\u043d\u043a\u0438\u043d\u0441": "Jenkins",
    "\u0434\u0436\u0438 \u0430\u0440 \u043f\u0438 \u0441\u0438": "gRPC",
    "\u0434\u0436\u0438 \u0434\u0430\u0431\u043b\u044e \u0442\u0438": "JWT",
    "\u0434\u0436\u0438 \u043f\u0438 \u044e": "GPU",
    "\u0434\u0436\u0438 \u0441\u0438 \u043f\u0438": "GCP",
    "\u0434\u0436\u0438 \u044e \u0430\u0439": "GUI",
    "\u0434\u0436\u0438\u0440\u0430": "Jira",
    "\u0434\u0436\u0438\u0441\u0438\u043f\u0438": "GCP",
    "\u0434\u0436\u0438\u0441\u043e\u043d": "JSON",
    "\u0434\u0436\u0438\u044d\u0440\u043f\u0438\u0441\u0438": "gRPC",
    "\u0434\u0436\u0443\u043f\u0438\u0442\u0435\u0440": "Jupyter",
    "\u0434\u0438 \u044d\u0439\u0447 \u0441\u0438 \u043f\u0438": "DHCP",
    "\u0434\u0438 \u044d\u043d \u044d\u0441": "DNS",
    "\u0434\u0438\u0430\u0439\u0447\u0441\u0438\u043f\u0438": "DHCP",
    "\u0434\u0438\u043d\u0430\u043c\u043e \u0434\u0438\u0431\u0438": "DynamoDB",
    "\u0434\u043d\u0441": "DNS",
    "\u0434\u043e\u043a\u0435\u0440": "Docker",
    "\u0434\u043e\u043a\u0435\u0440 \u043a\u043e\u043c\u043f\u043e\u0437": "Docker Compose",
    "\u0434\u043e\u043a\u0435\u0440 \u043a\u043e\u043c\u043f\u043e\u0443\u0437": "Docker Compose",
    "\u0434\u043e\u0442 \u043d\u0435\u0442": ".NET",
    "\u0434\u043e\u0442\u043d\u0435\u0442": ".NET",
    "\u0435\u0439 \u043f\u0438 \u0430\u0439": "API",
    "\u0435\u043d\u0442\u0438\u0442\u0438 \u0444\u0440\u0435\u0439\u043c\u0432\u043e\u0440\u043a": "Entity Framework",
    "\u0435\u0440\u043f": "ERP",
    "\u0435\u0441\u043b\u0438\u043d\u0442": "ESLint",
    "\u0435\u0442\u0438\u044d\u043b": "ETL",
    "\u0438 \u0430\u0440 \u043f\u0438": "ERP",
    "\u0438 \u0441\u0438 \u0434\u0432\u0430": "Amazon EC2",
    "\u0438 \u0442\u0438 \u044d\u043b": "ETL",
    "\u0438\u0438 \u0434\u0432\u0430": "Yii2",
    "\u0438\u043a\u0441 \u044d\u043c \u044d\u043b": "XML",
    "\u0438\u043a\u0441\u043c\u044d\u043b": "XML",
    "\u0438\u043a\u0441\u044d\u043c\u044d\u043b": "XML",
    "\u0438\u043c\u0430\u043f": "IMAP",
    "\u0438\u043d\u0436\u0438\u043d\u0438\u043a\u0441": "Nginx",
    "\u0438\u043f": "IP",
    "\u0438\u043f \u0430\u0434\u0440\u0435\u0441": "IP",
    "\u0438\u043f \u0432\u0438 \u0447\u0435\u0442\u044b\u0440\u0435": "IPv4",
    "\u0438\u043f \u0432\u0438 \u0448\u0435\u0441\u0442\u044c": "IPv6",
    "\u0438\u0441\u043b\u0438\u043d\u0442": "ESLint",
    "\u0439\u0438 \u0434\u0432\u0430": "Yii2",
    "\u0439\u0438\u0438 \u0434\u0432\u0430": "Yii2",
    "\u043a\u0430\u0441\u0441\u0430\u043d\u0434\u0440\u0430": "Cassandra",
    "\u043a\u0430\u0444\u043a\u0430": "Kafka",
    "\u043a\u0438\u0431\u0430\u043d\u0430": "Kibana",
    "\u043a\u043b\u0430\u0443\u0434 \u0444\u043b\u044d\u0440": "Cloudflare",
    "\u043a\u043b\u0430\u0443\u0434\u0444\u043b\u044d\u0440": "Cloudflare",
    "\u043a\u043b\u0438": "CLI",
    "\u043a\u043b\u0438\u043a \u0445\u0430\u0443\u0441": "ClickHouse",
    "\u043a\u043b\u0438\u043a\u0445\u0430\u0443\u0441": "ClickHouse",
    "\u043a\u043e\u043d\u0444\u043b\u044e\u0435\u043d\u0441": "Confluence",
    "\u043a\u043e\u0442\u043b\u0438\u043d": "Kotlin",
    "\u043a\u0443\u0431\u0435\u0440": "Kubernetes",
    "\u043a\u0443\u0431\u0435\u0440\u043d\u0435\u0442\u0435\u0441": "Kubernetes",
    "\u043a\u0443\u0434\u0430": "CUDA",
    "\u043a\u044c\u044e \u044d\u0439": "QA",
    "\u043a\u044c\u044e\u044d\u0439": "QA",
    "\u043b\u0430\u0440\u0430\u0432\u0435\u043b": "Laravel",
    "\u043b\u0430\u0440\u0430\u0432\u0435\u043b\u044c": "Laravel",
    "\u043b\u0435\u0441": "Less",
    "\u043b\u0435\u0441\u0441": "Less",
    "\u043b\u0438\u043d\u0443\u043a\u0441": "Linux",
    "\u043b\u043e\u0430\u0434 \u0431\u0430\u043b\u0430\u043d\u0441\u0435\u0440": "Load Balancer",
    "\u043b\u043e\u0433\u0441\u0442\u0430\u0448": "Logstash",
    "\u043b\u043e\u0433\u0441\u0442\u044d\u0448": "Logstash",
    "\u043b\u043e\u0434 \u0431\u0430\u043b\u0430\u043d\u0441\u0435\u0440": "Load Balancer",
    "\u043b\u044d\u0440\u0430\u0432\u0435\u043b": "Laravel",
    "\u043b\u044f\u043c\u0431\u0434\u0430": "AWS Lambda",
    "\u043c\u0430\u0439 \u044d\u0441 \u043a\u044c\u044e \u044d\u043b": "MySQL",
    "\u043c\u0430\u0439\u0441\u043a\u044c\u044e\u044d\u043b": "MySQL",
    "\u043c\u0430\u0440\u0432\u0435\u043b": "Laravel",
    "\u043c\u0430\u0440\u0438\u0430\u0434\u0431": "MariaDB",
    "\u043c\u0430\u0440\u0438\u044f \u0434\u0438\u0431\u0438": "MariaDB",
    "\u043c\u0430\u0442\u0435\u0440\u0438\u0430\u043b \u0443\u0430\u0439": "Material UI",
    "\u043c\u0430\u0442\u0435\u0440\u0438\u0430\u043b \u044e\u0430\u0439": "Material UI",
    "\u043c\u0438\u043a\u0440\u043e \u0441\u0435\u0440\u0432\u0438\u0441\u044b": "Microservices",
    "\u043c\u0438\u043a\u0440\u043e\u0441\u0435\u0440\u0432\u0438\u0441\u044b": "Microservices",
    "\u043c\u043e\u0431 \u0438\u043a\u0441": "MobX",
    "\u043c\u043e\u0431\u0438\u043a\u0441": "MobX",
    "\u043c\u043e\u043d\u0433\u043e \u0434\u0438\u0431\u0438": "MongoDB",
    "\u043c\u043e\u043d\u0433\u043e\u0434\u0431": "MongoDB",
    "\u043c\u043e\u043d\u043e\u043b\u0438\u0442": "Monolith",
    "\u043d\u0430\u043a\u0441\u0442 \u0434\u0436\u0438 \u044d\u0441": "Nuxt.js",
    "\u043d\u0430\u043c \u043f\u0430\u0439": "NumPy",
    "\u043d\u0430\u043c\u043f\u0430\u0439": "NumPy",
    "\u043d\u0430\u0441": "NAS",
    "\u043d\u0430\u0442": "NAT",
    "\u043d\u0434\u0436\u0438\u043d\u0438\u043a\u0441": "Nginx",
    "\u043d\u0435\u043a\u0441\u0442 \u0434\u0436\u0438 \u044d\u0441": "Next.js",
    "\u043d\u0435\u043a\u0441\u0442\u0434\u0436\u0441": "Next.js",
    "\u043d\u0435\u0441\u0442 \u0434\u0436\u0438 \u044d\u0441": "NestJS",
    "\u043d\u0435\u0441\u0442\u0434\u0436\u0441": "NestJS",
    "\u043d\u0435\u0442\u043b\u0438\u0444\u0430\u0439": "Netlify",
    "\u043d\u043e \u0441\u0438\u043a\u0432\u0435\u043b": "NoSQL",
    "\u043d\u043e\u0434 \u0434\u0436\u0438 \u044d\u0441": "Node.js",
    "\u043d\u043e\u0434\u0436\u0441": "Node.js",
    "\u043d\u043e\u0441\u043a\u044c\u044e\u044d\u043b": "NoSQL",
    "\u043d\u043e\u0443\u0434 \u0434\u0436\u0438 \u044d\u0441": "Node.js",
    "\u043d\u044e\u043a\u0441\u0442": "Nuxt.js",
    "\u043e \u0430\u0432\u0442": "OAuth",
    "\u043e \u0430\u0440 \u044d\u043c": "ORM",
    "\u043e \u0430\u0443\u0442": "OAuth",
    "\u043e\u0430\u0443\u0442": "OAuth",
    "\u043e\u043f\u0435\u043d \u0430\u0439\u0434\u0438 \u043a\u043e\u043d\u043d\u0435\u043a\u0442": "OpenID Connect",
    "\u043e\u043f\u0435\u043d \u0441\u0438 \u0432\u0438": "OpenCV",
    "\u043e\u043f\u0435\u043d\u0430\u0439\u0434\u0438 \u043a\u043e\u043d\u043d\u0435\u043a\u0442": "OpenID Connect",
    "\u043e\u043f\u0435\u043d\u0441\u0438\u0432\u0438": "OpenCV",
    "\u043e\u0440\u0430\u043a\u043b \u0434\u0430\u0442\u0430\u0431\u0435\u0439\u0441": "Oracle Database",
    "\u043e\u0440\u0430\u043a\u043b \u0434\u0438\u0431\u0438": "Oracle Database",
    "\u043e\u0440\u044d\u043c": "ORM",
    "\u043e\u0445\u0430\u0443\u0442": "OAuth",
    "\u043f\u0430\u0439 \u0442\u043e\u0440\u0447": "PyTorch",
    "\u043f\u0430\u0439\u0442\u043e\u043d": "Python",
    "\u043f\u0430\u0439\u0442\u043e\u0440\u0447": "PyTorch",
    "\u043f\u0430\u043d\u0434\u0430\u0441": "Pandas",
    "\u043f\u0430\u0443\u044d\u0440\u0448\u0435\u043b\u043b": "PowerShell",
    "\u043f\u0438 \u044d\u0439\u0447 \u043f\u0438": "PHP",
    "\u043f\u0438\u0442\u043e\u043d": "Python",
    "\u043f\u043e\u0432\u0435\u0440\u0448\u0435\u043b\u043b": "PowerShell",
    "\u043f\u043e\u043f \u0442\u0440\u0438": "POP3",
    "\u043f\u043e\u043f\u0442\u0440\u0438": "POP3",
    "\u043f\u043e\u0441\u0442\u0433\u0440\u0435\u0441": "PostgreSQL",
    "\u043f\u043e\u0441\u0442\u0433\u0440\u0435\u0441 \u044d\u0441 \u043a\u044c\u044e \u044d\u043b": "PostgreSQL",
    "\u043f\u043e\u0441\u0442\u0433\u0440\u0435\u0441\u043a\u044c\u044e\u044d\u043b": "PostgreSQL",
    "\u043f\u0440\u0435\u0442\u044c\u0435\u0440": "Prettier",
    "\u043f\u0440\u0438\u0442\u0442\u0438\u0435\u0440": "Prettier",
    "\u043f\u0440\u043e\u043a\u0441\u043c\u043e\u043a\u0441": "Proxmox",
    "\u043f\u0440\u043e\u043c\u0435\u0442\u0435\u0439": "Prometheus",
    "\u043f\u0440\u043e\u043c\u0435\u0442\u0435\u0443\u0441": "Prometheus",
    "\u043f\u0445\u043f": "PHP",
    "\u0440\u0430\u0431\u0431\u0438\u0442 \u044d\u043c \u043a\u044c\u044e": "RabbitMQ",
    "\u0440\u0430\u043c": "RAM",
    "\u0440\u0430\u0441\u0442": "Rust",
    "\u0440\u0435\u0430\u043a\u0442": "React",
    "\u0440\u0435\u0432\u0435\u0440\u0441 \u043f\u0440\u043e\u043a\u0441\u0438": "Reverse Proxy",
    "\u0440\u0435\u0432\u0435\u0440\u0441\u043f\u0440\u043e\u043a\u0441\u0438": "Reverse Proxy",
    "\u0440\u0435\u0433\u0435\u043a\u0441": "Regex",
    "\u0440\u0435\u0434\u0430\u043a\u0441": "Redux",
    "\u0440\u0435\u0434\u0436\u0435\u043a\u0441": "Regex",
    "\u0440\u0435\u0434\u0438\u0441": "Redis",
    "\u0440\u0435\u0434\u0443\u043a\u0441": "Redux",
    "\u0440\u0435\u0439\u0434": "RAID",
    "\u0440\u0435\u0441\u0442 \u0430\u043f\u0438": "REST API",
    "\u0440\u0435\u0441\u0442 \u044d\u043f\u0438\u0430\u0439": "REST API",
    "\u0440\u0435\u0441\u0442\u0444\u0443\u043b": "RESTful",
    "\u0440\u0438\u0430\u043a\u0442": "React",
    "\u0440\u0443\u0431\u0438": "Ruby",
    "\u0440\u044d\u0431\u0431\u0438\u0442 \u044d\u043c \u043a\u044c\u044e": "RabbitMQ",
    "\u0440\u044d\u0441\u0442 \u0430\u043f\u0438": "REST API",
    "\u0440\u044d\u0441\u0442\u0444\u0443\u043b": "RESTful",
    "\u0441\u0430\u0439\u043a\u0438\u0442 \u043b\u0435\u0440\u043d": "scikit-learn",
    "\u0441\u0430\u043c\u043b": "SAML",
    "\u0441\u0430\u043d": "SAN",
    "\u0441\u0430\u0441": "Sass",
    "\u0441\u0430\u0441\u0441": "Sass",
    "\u0441\u0432\u0435\u043b\u0442": "Svelte",
    "\u0441\u0432\u0438\u0444\u0442": "Swift",
    "\u0441\u0432\u044d\u043b\u0442": "Svelte",
    "\u0441\u0434\u043d": "CDN",
    "\u0441\u0435\u043d\u0442\u0440\u0438": "Sentry",
    "\u0441\u0435\u0440\u043a\u043b \u0441\u0438 \u0430\u0439": "CircleCI",
    "\u0441\u0435\u0440\u043a\u043b\u0441\u0438\u0430\u0439": "CircleCI",
    "\u0441\u0438 \u0430\u0439 \u0441\u0438 \u0434\u0438": "CI/CD",
    "\u0441\u0438 \u0430\u0440 \u044d\u043c": "CRM",
    "\u0441\u0438 \u0434\u0438 \u044d\u043d": "CDN",
    "\u0441\u0438 \u043f\u0438 \u044e": "CPU",
    "\u0441\u0438 \u043f\u043b\u044e\u0441 \u043f\u043b\u044e\u0441": "C++",
    "\u0441\u0438 \u043f\u043b\u044e\u0441\u043f\u043b\u044e\u0441": "C++",
    "\u0441\u0438 \u0448\u0430\u0440\u043f": "C#",
    "\u0441\u0438 \u044d\u043b \u0430\u0439": "CLI",
    "\u0441\u0438 \u044d\u0441 \u0432\u0438": "CSV",
    "\u0441\u0438 \u044d\u0441 \u044d\u0441": "CSS",
    "\u0441\u0438\u0430\u0439 \u0441\u0438\u0434\u0438": "CI/CD",
    "\u0441\u0438\u0434\u0438\u044d\u043d": "CDN",
    "\u0441\u0438\u043a\u0432\u0435\u043b": "SQL",
    "\u0441\u0438\u043a\u0432\u0435\u043b\u0430\u0439\u0442": "SQLite",
    "\u0441\u0438\u043c\u0444\u043e\u043d\u0438": "Symfony",
    "\u0441\u0438\u043c\u0444\u043e\u043d\u0438\u044f": "Symfony",
    "\u0441\u0438\u0448\u0430\u0440\u043f": "C#",
    "\u0441\u0438\u044d\u0441\u0432\u0438": "CSV",
    "\u0441\u0438\u044d\u0441\u044d\u0441": "SCSS",
    "\u0441\u043a\u0430\u0439\u043a\u0438\u0442 \u043b\u0435\u0440\u043d": "scikit-learn",
    "\u0441\u043a\u0430\u0441\u0441": "SCSS",
    "\u0441\u043c\u0442\u043f": "SMTP",
    "\u0441\u043f\u0440\u0438\u043d\u0433": "Spring",
    "\u0441\u043f\u0440\u0438\u043d\u0433 \u0431\u0443\u0442": "Spring Boot",
    "\u0441\u043f\u0440\u0438\u043d\u0433\u0431\u0443\u0442": "Spring Boot",
    "\u0441\u0440\u043c": "CRM",
    "\u0441\u0441\u0434": "SSD",
    "\u0441\u0441\u043b": "SSL",
    "\u0441\u0441\u043e": "SSO",
    "\u0441\u0441\u0441": "CSS",
    "\u0441\u0442\u043e\u0440\u0438 \u0431\u0443\u043a": "Storybook",
    "\u0441\u0442\u043e\u0440\u0438\u0431\u0443\u043a": "Storybook",
    "\u0441\u0448": "SSH",
    "\u0441\u044c\u044e\u0434\u0430": "CUDA",
    "\u0442\u0430\u0439\u043f \u0441\u043a\u0440\u0438\u043f\u0442": "TypeScript",
    "\u0442\u0430\u0439\u043f\u0441\u043a\u0440\u0438\u043f\u0442": "TypeScript",
    "\u0442\u0435\u0439\u043b\u0432\u0438\u043d\u0434": "Tailwind CSS",
    "\u0442\u0435\u0439\u043b\u0432\u0438\u043d\u0434 \u0441\u0438\u044d\u0441\u044d\u0441": "Tailwind CSS",
    "\u0442\u0435\u043d\u0437\u043e\u0440\u0444\u043b\u043e\u0443": "TensorFlow",
    "\u0442\u0435\u043d\u0441\u043e\u0440 \u0444\u043b\u043e\u0443": "TensorFlow",
    "\u0442\u0435\u0440\u0430\u0444\u043e\u0440\u043c": "Terraform",
    "\u0442\u0435\u0440\u0440\u0430\u0444\u043e\u0440\u043c": "Terraform",
    "\u0442\u0438 \u0441\u0438 \u043f\u0438": "TCP",
    "\u0442\u0438 \u044d\u043b \u044d\u0441": "TLS",
    "\u0442\u0438\u043c \u0441\u0438\u0442\u0438": "TeamCity",
    "\u0442\u0438\u043c\u0441\u0438\u0442\u0438": "TeamCity",
    "\u0442\u0438\u0441\u0438\u043f\u0438": "TCP",
    "\u0442\u043b\u0441": "TLS",
    "\u0442\u0440\u0430\u0432\u0438\u0441 \u0441\u0438 \u0430\u0439": "Travis CI",
    "\u0442\u0440\u0435\u0432\u0438\u0441 \u0441\u0438 \u0430\u0439": "Travis CI",
    "\u0442\u044d \u0441\u0438 \u043f\u0438": "TCP",
    "\u0443 \u0434\u0438 \u043f\u0438": "UDP",
    "\u0443\u0431\u0443\u043d\u0442\u0443": "Ubuntu",
    "\u0444\u0430\u0439\u0440\u0431\u0435\u0439\u0441": "Firebase",
    "\u0444\u0430\u0441\u0442 \u0430\u043f\u0438": "FastAPI",
    "\u0444\u0430\u0441\u0442\u0430\u043f\u0438": "FastAPI",
    "\u0444\u043b\u0430\u0441\u043a": "Flask",
    "\u0445\u0430\u0439\u0431\u0435\u0440\u043d\u0435\u0439\u0442": "Hibernate",
    "\u0445\u0434\u0434": "HDD",
    "\u0445\u0435\u043b\u043c": "Helm",
    "\u0445\u0438\u0431\u0435\u0440\u043d\u0435\u0439\u0442": "Hibernate",
    "\u0446\u0435\u043d\u0442\u043e\u0441": "CentOS",
    "\u0446\u043f\u0443": "CPU",
    "\u044d\u0436\u0443\u0440": "Azure",
    "\u044d\u0439 \u0434\u0430\u0431\u043b\u044e \u044d\u0441": "AWS",
    "\u044d\u0439 \u0434\u0430\u0431\u043b\u044e \u044d\u0441 \u043b\u044f\u043c\u0431\u0434\u0430": "AWS Lambda",
    "\u044d\u0439 \u043f\u0438 \u0430\u0439": "API",
    "\u044d\u0439\u0447 \u0434\u0438 \u0434\u0438": "HDD",
    "\u044d\u0439\u0447 \u0442\u0438 \u0442\u0438 \u043f\u0438": "HTTP",
    "\u044d\u0439\u0447 \u0442\u0438 \u0442\u0438 \u043f\u0438 \u044d\u0441": "HTTPS",
    "\u044d\u0439\u0447 \u0442\u0438 \u044d\u043c \u044d\u043b": "HTML",
    "\u044d\u043a\u0441\u043f\u0440\u0435\u0441\u0441": "Express.js",
    "\u044d\u043a\u0441\u043f\u0440\u0435\u0441\u0441 \u0434\u0436\u0438 \u044d\u0441": "Express.js",
    "\u044d\u043b \u0434\u0430\u043f": "LDAP",
    "\u044d\u043b \u0434\u0438 \u044d\u0439 \u043f\u0438": "LDAP",
    "\u044d\u043b\u0430\u0441\u0442\u0438\u043a \u0441\u0435\u0440\u0447": "Elasticsearch",
    "\u044d\u043b\u0430\u0441\u0442\u0438\u043a\u0441\u0435\u0440\u0447": "Elasticsearch",
    "\u044d\u043b\u0434\u0430\u043f": "LDAP",
    "\u044d\u043c \u044d\u0441 \u0441\u0438\u043a\u0432\u0435\u043b \u0441\u0435\u0440\u0432\u0435\u0440": "MS SQL Server",
    "\u044d\u043c\u044d\u0441\u0441\u0438\u043a\u0432\u0435\u043b \u0441\u0435\u0440\u0432\u0435\u0440": "MS SQL Server",
    "\u044d\u043d \u044d\u0439 \u0442\u0438": "NAT",
    "\u044d\u043d \u044d\u0439 \u044d\u0441": "NAS",
    "\u044d\u043d\u0434\u0436\u0438\u043d\u0438\u043a\u0441": "Nginx",
    "\u044d\u043d\u0441\u0438\u0431\u043b": "Ansible",
    "\u044d\u043d\u0442\u0438\u0442\u0438 \u0444\u0440\u0435\u0439\u043c\u0432\u043e\u0440\u043a": "Entity Framework",
    "\u044d\u043f\u0438\u0430\u0439": "API",
    "\u044d\u0441 \u0434\u0438 \u043a\u0435\u0439": "SDK",
    "\u044d\u0441 \u043a\u044c\u044e \u044d\u043b": "SQL",
    "\u044d\u0441 \u0441\u0438 \u044d\u0441 \u044d\u0441": "SCSS",
    "\u044d\u0441 \u0442\u0440\u0438": "Amazon S3",
    "\u044d\u0441 \u044d\u0439 \u044d\u043c \u044d\u043b": "SAML",
    "\u044d\u0441 \u044d\u0439 \u044d\u043d": "SAN",
    "\u044d\u0441 \u044d\u043c \u0442\u0438 \u043f\u0438": "SMTP",
    "\u044d\u0441 \u044d\u0441 \u0434\u0438": "SSD",
    "\u044d\u0441 \u044d\u0441 \u043e": "SSO",
    "\u044d\u0441 \u044d\u0441 \u044d\u0439\u0447": "SSH",
    "\u044d\u0441 \u044d\u0441 \u044d\u043b": "SSL",
    "\u044d\u0441\u0434\u0438\u043a\u0435\u0439": "SDK",
    "\u044d\u0441\u043a\u044c\u044e\u043b\u0430\u0439\u0442": "SQLite",
    "\u044d\u0441\u0448\u0430": "SSH",
    "\u044e \u0430\u0440 \u0430\u0439": "URI",
    "\u044e \u0434\u0438 \u043f\u0438": "UDP",
    "\u044e \u0438 \u044d\u0444 \u0430\u0439": "UEFI",
    "\u044e \u044d\u0440 \u044d\u043b": "URL",
    "\u044e\u0434\u043f": "UDP",
    "\u044e\u0438\u0444\u0438": "UEFI",
    "\u044e\u043f\u0438\u0442\u0435\u0440": "Jupyter",
    "\u044e\u0440\u0430\u0439": "URI",
    "\u044e\u0440\u044d\u043b": "URL",
    "\u044f \u043c\u043b": "YAML",
    "\u044f\u043c\u0435\u043b": "YAML",
    "\u044f\u043c\u043b": "YAML",
    "\u044f\u043d\u0434\u0435\u043a\u0441 \u043a\u043b\u0430\u0443\u0434": "Yandex Cloud",
    "\u044f\u043d\u0434\u0435\u043a\u0441\u043a\u043b\u0430\u0443\u0434": "Yandex Cloud"
}

_ACTIVE_TECHNICAL_MODES = tuple()
_TECHNICAL_TERMS_CACHE_KEY = None
_TECHNICAL_TERMS_PAYLOAD = None
_TECHNICAL_TERMS_SOURCE = "built-in defaults"
_RESOLVED_TERMS_CACHE = {}


def default_technical_terms_payload():
    return {
        "enabled": True,
        "description": "\u0413\u043b\u0430\u0432\u043d\u044b\u0439 \u0440\u0435\u0436\u0438\u043c \u043e\u0441\u0442\u0430\u0435\u0442\u0441\u044f \u043d\u0435\u0439\u0442\u0440\u0430\u043b\u044c\u043d\u044b\u043c. IT-\u0441\u043b\u043e\u0432\u0430\u0440\u044c \u0436\u0438\u0432\u0435\u0442 \u0432 \u043e\u0442\u0434\u0435\u043b\u044c\u043d\u043e\u043c \u0440\u0435\u0436\u0438\u043c\u0435, \u0447\u0442\u043e\u0431\u044b \u043d\u0435 \u043b\u043e\u043c\u0430\u0442\u044c \u043e\u0431\u044b\u0447\u043d\u044b\u0435 \u0434\u0438\u0430\u043b\u043e\u0433\u0438.",
        "replacements": {},
        "modes": {
            "it_mode": {
                "label": "IT \u0440\u0435\u0436\u0438\u043c",
                "description": "\u0420\u0435\u0436\u0438\u043c \u0443\u0441\u0438\u043b\u0435\u043d\u043d\u043e\u0439 \u043d\u043e\u0440\u043c\u0430\u043b\u0438\u0437\u0430\u0446\u0438\u0438 \u0442\u0435\u0445\u043d\u0438\u0447\u0435\u0441\u043a\u0438\u0445 \u0442\u0435\u0440\u043c\u0438\u043d\u043e\u0432, \u0430\u0431\u0431\u0440\u0435\u0432\u0438\u0430\u0442\u0443\u0440, \u0444\u0440\u0435\u0439\u043c\u0432\u043e\u0440\u043a\u043e\u0432, \u0431\u0430\u0437 \u0434\u0430\u043d\u043d\u044b\u0445 \u0438 DevOps-\u0441\u0442\u0435\u043a\u0430.",
                "replacements": dict(IT_MODE_REPLACEMENTS),
            }
        },
    }


def default_technical_terms_content():
    return json.dumps(default_technical_terms_payload(), ensure_ascii=False, indent=2)


def _technical_terms_cache_key():
    try:
        stat = _runtime.TECHNICAL_TERMS_PATH.stat()
        return (str(_runtime.TECHNICAL_TERMS_PATH), stat.st_mtime_ns, stat.st_size)
    except OSError:
        return (str(_runtime.TECHNICAL_TERMS_PATH), None, None)


def _normalize_mapping(raw_mapping):
    normalized = {}
    if isinstance(raw_mapping, dict):
        for raw_key, raw_value in raw_mapping.items():
            key = _runtime.normalize_name(raw_key)
            value = " ".join(str(raw_value or "").split())
            if key and value:
                normalized[key] = value
    return normalized


def load_technical_terms(force=False):
    global _TECHNICAL_TERMS_CACHE_KEY, _TECHNICAL_TERMS_PAYLOAD, _TECHNICAL_TERMS_SOURCE, _RESOLVED_TERMS_CACHE

    cache_key = _technical_terms_cache_key()
    if not force and cache_key == _TECHNICAL_TERMS_CACHE_KEY and _TECHNICAL_TERMS_PAYLOAD is not None:
        return _TECHNICAL_TERMS_PAYLOAD

    payload = default_technical_terms_payload()
    source = "built-in defaults"

    if _runtime.TECHNICAL_TERMS_PATH.exists():
        try:
            loaded = json.loads(_runtime.TECHNICAL_TERMS_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
                source = str(_runtime.TECHNICAL_TERMS_PATH)
            else:
                raise ValueError("Technical terms file must contain a JSON object.")
        except Exception:
            _runtime.LOGGER.exception("Failed to load technical terms from %s, using defaults", _runtime.TECHNICAL_TERMS_PATH)

    enabled = bool(payload.get("enabled", True))
    global_replacements = _normalize_mapping(payload.get("replacements", {}))
    modes = {}

    raw_modes = payload.get("modes", {})
    if isinstance(raw_modes, dict):
        for raw_mode_name, raw_mode_payload in raw_modes.items():
            mode_name = " ".join(str(raw_mode_name or "").strip().split())
            if not mode_name or not isinstance(raw_mode_payload, dict):
                continue

            replacements = _normalize_mapping(raw_mode_payload.get("replacements", {}))
            modes[mode_name] = {
                "label": " ".join(str(raw_mode_payload.get("label") or mode_name).split()),
                "description": " ".join(str(raw_mode_payload.get("description") or "").split()),
                "replacements": replacements,
                "term_count": len(replacements),
            }

    _TECHNICAL_TERMS_CACHE_KEY = cache_key
    _TECHNICAL_TERMS_SOURCE = source
    _TECHNICAL_TERMS_PAYLOAD = {
        "enabled": enabled,
        "replacements": global_replacements,
        "modes": modes,
        "source": source,
    }
    _RESOLVED_TERMS_CACHE = {}
    _runtime.LOGGER.info(
        "Technical terms loaded. enabled=%s global_terms=%s modes=%s source=%s",
        enabled,
        len(global_replacements),
        {name: info["term_count"] for name, info in modes.items()},
        source,
    )
    return _TECHNICAL_TERMS_PAYLOAD


def get_available_technical_modes():
    return load_technical_terms().get("modes", {})


def set_active_technical_modes(modes):
    global _ACTIVE_TECHNICAL_MODES

    available = get_available_technical_modes()
    normalized = []
    for raw_mode in modes or ():
        mode_name = " ".join(str(raw_mode or "").strip().split())
        if mode_name and mode_name in available and mode_name not in normalized:
            normalized.append(mode_name)
    _ACTIVE_TECHNICAL_MODES = tuple(normalized)
    return _ACTIVE_TECHNICAL_MODES


def get_active_technical_modes():
    return _ACTIVE_TECHNICAL_MODES


def resolve_active_technical_terms(active_modes=None):
    payload = load_technical_terms()
    if not payload.get("enabled", True):
        return {}, None

    mode_names = tuple(active_modes if active_modes is not None else get_active_technical_modes())
    if mode_names in _RESOLVED_TERMS_CACHE:
        return _RESOLVED_TERMS_CACHE[mode_names]

    combined = dict(payload.get("replacements", {}))
    for mode_name in mode_names:
        mode_payload = payload.get("modes", {}).get(mode_name)
        if mode_payload:
            combined.update(mode_payload.get("replacements", {}))

    if not combined:
        resolved = ({}, None)
        _RESOLVED_TERMS_CACHE[mode_names] = resolved
        return resolved

    variants = sorted(combined, key=len, reverse=True)
    pattern = re.compile(r"(?<!\w)(" + "|".join(re.escape(item) for item in variants) + r")(?!\w)", re.IGNORECASE)
    resolved = (combined, pattern)
    _RESOLVED_TERMS_CACHE[mode_names] = resolved
    return resolved


def apply_technical_term_replacements(text, log_changes=False, active_modes=None):
    normalized = " ".join((text or "").split())
    if not normalized:
        return ""

    replacements, pattern = resolve_active_technical_terms(active_modes=active_modes)
    if not replacements or pattern is None:
        return normalized

    def repl(match):
        key = _runtime.normalize_name(match.group(0))
        return replacements.get(key, match.group(0))

    corrected = pattern.sub(repl, normalized)
    if log_changes and corrected != normalized:
        active = list(active_modes if active_modes is not None else get_active_technical_modes())
        _runtime.LOGGER.info(
            "Technical replacements applied. modes=%s before=%s after=%s",
            active,
            _runtime.short_text(normalized, 200),
            _runtime.short_text(corrected, 200),
        )
    return corrected


_runtime.default_technical_terms_payload = default_technical_terms_payload
_runtime.default_technical_terms_content = default_technical_terms_content
_runtime.load_technical_terms = load_technical_terms
_runtime.apply_technical_term_replacements = apply_technical_term_replacements
_runtime.get_available_technical_modes = get_available_technical_modes
_runtime.resolve_active_technical_terms = resolve_active_technical_terms
_runtime.set_active_technical_modes = set_active_technical_modes
_runtime.get_active_technical_modes = get_active_technical_modes

_runtime.ensure_text_file(_runtime.TECHNICAL_TERMS_PATH, default_technical_terms_content())
load_technical_terms(force=True)


class OperatorAssistApp(_base_mod.OperatorAssistApp):
    def __init__(self, root):
        self.mic_devices = []
        self.speaker_sources = []
        self.default_loopback_label = None
        super().__init__(root)
        self._push_active_term_modes()
        self._sync_it_mode_button()

    def _ensure_it_mode_state(self):
        saved_value = bool(getattr(self, "settings", {}).get("it_mode_enabled", False))
        if not hasattr(self, "it_mode_var"):
            self.it_mode_var = _runtime.tk.BooleanVar(value=saved_value)
        if not hasattr(self, "it_mode_button_var"):
            self.it_mode_button_var = _runtime.tk.StringVar()

    def _active_term_modes(self):
        return ("it_mode",) if bool(self.it_mode_var.get()) else tuple()

    def _push_active_term_modes(self):
        return set_active_technical_modes(self._active_term_modes())

    def _it_mode_term_count(self):
        return get_available_technical_modes().get("it_mode", {}).get("term_count", 0)

    def _sync_it_mode_button(self):
        enabled = bool(self.it_mode_var.get())
        self.it_mode_button_var.set("IT \u0440\u0435\u0436\u0438\u043c: \u0412\u041a\u041b" if enabled else "IT \u0440\u0435\u0436\u0438\u043c: \u0432\u044b\u043a\u043b")
        if hasattr(self, "it_mode_button"):
            if enabled:
                self.it_mode_button.configure(bg="#fff4df", fg="#5b4611")
            else:
                self.it_mode_button.configure(bg="#f6f8fb", fg="#17324d")

    def _update_it_mode_hint(self, speaker_source=None):
        if bool(self.it_mode_var.get()):
            message = (
                f"\u0410\u043a\u0442\u0438\u0432\u043d\u0430\u044f \u043c\u043e\u0434\u0435\u043b\u044c: {self._current_model_name()}. "
                f"IT \u0440\u0435\u0436\u0438\u043c \u0432\u043a\u043b\u044e\u0447\u0435\u043d, \u0430\u043a\u0442\u0438\u0432\u043d\u043e {self._it_mode_term_count()} \u043f\u0440\u0430\u0432\u0438\u043b \u0441\u043b\u043e\u0432\u0430\u0440\u044f."
            )
        else:
            message = (
                f"\u0410\u043a\u0442\u0438\u0432\u043d\u0430\u044f \u043c\u043e\u0434\u0435\u043b\u044c: {self._current_model_name()}. "
                "\u0420\u0430\u0441\u043f\u043e\u0437\u043d\u0430\u0432\u0430\u043d\u0438\u0435 \u0438\u0434\u0435\u0442 \u0431\u0435\u0437 IT-\u0441\u043b\u043e\u0432\u0430\u0440\u044f."
            )
        if speaker_source is not None:
            message = f"{message} \u0421\u043e\u0431\u0435\u0441\u0435\u0434\u043d\u0438\u043a \u0437\u0430\u0445\u0432\u0430\u0442\u044b\u0432\u0430\u0435\u0442\u0441\u044f \u0447\u0435\u0440\u0435\u0437 {speaker_source['mode_label']}."
        self.hint_var.set(message)

    def _make_loopback_label(self, name, source_id, seen_labels):
        label = f"WASAPI loopback: {name}"
        if label in seen_labels:
            tail = str(source_id).strip("{}")[-8:]
            label = f"{label} [{tail}]"
        seen_labels.add(label)
        return label

    def _apply_default_devices(self):
        mic_labels = [self._device_label(device) for device in self.mic_devices]
        speaker_labels = [source["label"] for source in self.speaker_sources]

        self.mic_combo["values"] = mic_labels
        self.speaker_combo["values"] = speaker_labels

        if not mic_labels:
            _runtime.LOGGER.warning("No microphone devices available")
            return

        if not speaker_labels:
            _runtime.LOGGER.warning("No speaker capture sources available")
            return

        saved_mic = self.settings.get("mic_device")
        saved_speaker = self.settings.get("speaker_device")

        mic_default = saved_mic if saved_mic in mic_labels else self._find_mic_label(("\u043c\u0438\u043a\u0440\u043e\u0444", "microphone", "mic input"))

        if saved_speaker in speaker_labels and saved_speaker.startswith("WASAPI loopback:"):
            speaker_default = saved_speaker
        elif self.default_loopback_label:
            speaker_default = self.default_loopback_label
        elif saved_speaker in speaker_labels:
            speaker_default = saved_speaker
        else:
            speaker_default = self._find_speaker_label()

        self.mic_device_var.set(mic_default or mic_labels[0])
        self.speaker_device_var.set(speaker_default or speaker_labels[0])

        _runtime.LOGGER.info(
            "Default devices selected in IT wrapper. mic=%s speaker=%s",
            self.mic_device_var.get(),
            self.speaker_device_var.get(),
        )

    def _save_settings(self):
        super()._save_settings()
        payload = {}
        if _runtime.SETTINGS_PATH.exists():
            try:
                loaded = json.loads(_runtime.SETTINGS_PATH.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    payload = loaded
            except Exception:
                _runtime.LOGGER.exception("Failed to reload settings before adding IT mode flag")
        payload["it_mode_enabled"] = bool(self.it_mode_var.get())
        _runtime.SETTINGS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        _runtime.LOGGER.info("Saved IT mode state: %s", payload["it_mode_enabled"])

    def _build_ui(self):
        self._ensure_it_mode_state()
        runtime = _base_mod._base_mod._base

        self.root.geometry("1360x860")
        self.root.minsize(1080, 700)
        self.root.configure(bg="#f3f6f9")

        shell = runtime.tk.Frame(self.root, bg="#f3f6f9")
        shell.pack(fill="both", expand=True)

        canvas = runtime.tk.Canvas(shell, bg="#f3f6f9", highlightthickness=0)
        scrollbar = runtime.ttk.Scrollbar(shell, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        wrapper = runtime.tk.Frame(canvas, bg="#f3f6f9")
        canvas_window = canvas.create_window((0, 0), window=wrapper, anchor="nw")

        def sync_scrollregion(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def fit_width(event):
            canvas.itemconfigure(canvas_window, width=event.width)

        def on_mousewheel(event):
            if event.delta:
                canvas.yview_scroll(int(-event.delta / 120), "units")
                return "break"
            return None

        wrapper.bind("<Configure>", sync_scrollregion)
        canvas.bind("<Configure>", fit_width)
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        self._main_canvas = canvas
        self._main_scrollbar = scrollbar

        outer = runtime.tk.Frame(wrapper, bg="#f3f6f9")
        outer.pack(fill="both", expand=True, padx=18, pady=18)

        header = runtime.tk.Frame(outer, bg="#f3f6f9")
        header.pack(fill="x", pady=(0, 12))

        runtime.tk.Label(
            header,
            text="Operator Assist",
            font=("Segoe UI", 24, "bold"),
            bg="#f3f6f9",
            fg="#17324d",
        ).pack(anchor="w")

        runtime.tk.Label(
            header,
            text="\u041e\u0434\u043d\u043e\u0432\u0440\u0435\u043c\u0435\u043d\u043d\u043e\u0435 \u0440\u0430\u0441\u043f\u043e\u0437\u043d\u0430\u0432\u0430\u043d\u0438\u0435 \u0432\u0430\u0448\u0435\u0433\u043e \u043c\u0438\u043a\u0440\u043e\u0444\u043e\u043d\u0430 \u0438 \u0441\u0438\u0441\u0442\u0435\u043c\u043d\u043e\u0433\u043e \u0437\u0432\u0443\u043a\u0430 \u0447\u0435\u0440\u0435\u0437 WASAPI loopback \u0438\u043b\u0438 \u0437\u0430\u043f\u0430\u0441\u043d\u043e\u0439 \u0432\u0445\u043e\u0434",
            font=("Segoe UI", 11),
            bg="#f3f6f9",
            fg="#5f7184",
        ).pack(anchor="w", pady=(2, 0))

        controls = runtime.tk.Frame(outer, bg="white", highlightbackground="#d9e2ec", highlightthickness=1)
        controls.pack(fill="x", pady=(0, 12))
        controls.configure(padx=16, pady=16)

        runtime.tk.Label(controls, text="\u041c\u043e\u0439 \u043c\u0438\u043a\u0440\u043e\u0444\u043e\u043d", bg="white", fg="#5f7184", font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w")
        runtime.tk.Label(controls, text="\u0421\u043e\u0431\u0435\u0441\u0435\u0434\u043d\u0438\u043a / \u0441\u0438\u0441\u0442\u0435\u043c\u043d\u044b\u0439 \u0437\u0432\u0443\u043a", bg="white", fg="#5f7184", font=("Segoe UI", 10)).grid(row=0, column=1, sticky="w", padx=(16, 0))

        self.mic_combo = runtime.ttk.Combobox(controls, textvariable=self.mic_device_var, state="readonly", width=48)
        self.mic_combo.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.speaker_combo = runtime.ttk.Combobox(controls, textvariable=self.speaker_device_var, state="readonly", width=48)
        self.speaker_combo.grid(row=1, column=1, sticky="ew", padx=(16, 0), pady=(6, 0))

        buttons = runtime.tk.Frame(controls, bg="white")
        buttons.grid(row=1, column=2, padx=(16, 0), sticky="e")

        self.start_button = runtime.tk.Button(buttons, text="\u0421\u0442\u0430\u0440\u0442", command=self.start_transcription, bg="#0f766e", fg="white", relief="flat", padx=16, pady=10, state="disabled")
        self.start_button.pack(side="left", padx=(0, 8))
        self.stop_button = runtime.tk.Button(buttons, text="\u0421\u0442\u043e\u043f", command=self.stop_transcription, bg="#e7eef5", fg="#17324d", relief="flat", padx=16, pady=10, state="disabled")
        self.stop_button.pack(side="left", padx=(0, 8))
        runtime.tk.Button(buttons, text="\u041e\u0431\u043d\u043e\u0432\u0438\u0442\u044c \u0443\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432\u0430", command=self.refresh_devices, bg="#e7eef5", fg="#17324d", relief="flat", padx=16, pady=10).pack(side="left")

        controls.grid_columnconfigure(0, weight=1)
        controls.grid_columnconfigure(1, weight=1)

        action_bar = runtime.tk.Frame(outer, bg="white", highlightbackground="#d9e2ec", highlightthickness=1)
        action_bar.pack(fill="x", pady=(0, 12))
        action_bar.configure(padx=16, pady=12)

        runtime.tk.Label(action_bar, textvariable=self.status_var, bg="white", fg="#0f766e", font=("Segoe UI", 11, "bold")).pack(side="left")
        runtime.tk.Label(action_bar, textvariable=self.hint_var, bg="white", fg="#5f7184", font=("Segoe UI", 10)).pack(side="left", padx=(18, 0))

        actions_right = runtime.tk.Frame(action_bar, bg="white")
        actions_right.pack(side="right")
        self.it_mode_button = runtime.tk.Button(actions_right, textvariable=self.it_mode_button_var, command=self.toggle_it_mode, bg="#f6f8fb", fg="#17324d", relief="flat", padx=12, pady=8)
        self.it_mode_button.pack(side="left", padx=(0, 8))
        runtime.tk.Button(actions_right, text="\u041a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0441\u043e\u0431\u0435\u0441\u0435\u0434\u043d\u0438\u043a\u0430", command=self.copy_speaker_text, bg="#fff4df", fg="#5b4611", relief="flat", padx=12, pady=8).pack(side="left", padx=(0, 8))
        runtime.tk.Button(actions_right, text="\u041a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0432\u0441\u0451", command=self.copy_all_text, bg="#eef6ff", fg="#17406d", relief="flat", padx=12, pady=8).pack(side="left", padx=(0, 8))
        runtime.tk.Button(actions_right, text="\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c TXT", command=self.save_transcript, bg="#e8f8f2", fg="#0b5d4f", relief="flat", padx=12, pady=8).pack(side="left", padx=(0, 8))
        runtime.tk.Button(actions_right, text="\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u043b\u043e\u0433\u0438", command=self.open_logs_folder, bg="#f3efff", fg="#4b2d8d", relief="flat", padx=12, pady=8).pack(side="left", padx=(0, 8))
        runtime.tk.Button(actions_right, text="\u041e\u0447\u0438\u0441\u0442\u0438\u0442\u044c", command=self.clear_text, bg="#fdebec", fg="#8a2f39", relief="flat", padx=12, pady=8).pack(side="left")

        panel_grid = runtime.tk.Frame(outer, bg="#f3f6f9")
        panel_grid.pack(fill="both", expand=True)
        panel_grid.grid_columnconfigure(0, weight=1)
        panel_grid.grid_columnconfigure(1, weight=1)
        panel_grid.grid_rowconfigure(0, weight=1)

        self.my_text = self._build_panel(panel_grid, 0, "\u042f / \u043e\u043f\u0435\u0440\u0430\u0442\u043e\u0440", self.my_partial_var)
        self.speaker_text = self._build_panel(panel_grid, 1, "\u0421\u043e\u0431\u0435\u0441\u0435\u0434\u043d\u0438\u043a", self.speaker_partial_var)

        self._build_chat_bridge(outer)
        if hasattr(self, "ai_prompt_text"):
            self.ai_prompt_text.configure(height=8)

        self._sync_it_mode_button()
        self.root.after(50, sync_scrollregion)

    def toggle_it_mode(self):
        self.it_mode_var.set(not bool(self.it_mode_var.get()))
        load_technical_terms(force=True)
        active_modes = self._push_active_term_modes()
        self._sync_it_mode_button()
        self._save_settings()

        if active_modes:
            self.hint_var.set(
                f"IT \u0440\u0435\u0436\u0438\u043c \u0432\u043a\u043b\u044e\u0447\u0435\u043d. \u0410\u043a\u0442\u0438\u0432\u043d\u043e {self._it_mode_term_count()} \u043f\u0440\u0430\u0432\u0438\u043b \u0442\u0435\u0445\u043d\u0438\u0447\u0435\u0441\u043a\u043e\u0433\u043e \u0441\u043b\u043e\u0432\u0430\u0440\u044f."
            )
        else:
            self.hint_var.set("IT \u0440\u0435\u0436\u0438\u043c \u0432\u044b\u043a\u043b\u044e\u0447\u0435\u043d. \u0420\u0430\u0441\u043f\u043e\u0437\u043d\u0430\u0432\u0430\u043d\u0438\u0435 \u0438\u0434\u0435\u0442 \u0431\u0435\u0437 \u0442\u0435\u0445\u043d\u0438\u0447\u0435\u0441\u043a\u043e\u0433\u043e \u0441\u043b\u043e\u0432\u0430\u0440\u044f.")

        _runtime.LOGGER.info(
            "IT mode toggled. active_modes=%s rules=%s",
            list(active_modes),
            self._it_mode_term_count(),
        )

    def start_transcription(self):
        load_technical_terms(force=True)
        active_modes = self._push_active_term_modes()
        speaker_source = self._selected_speaker_source()
        super().start_transcription()
        if self.workers and "speaker" in self.workers:
            self._update_it_mode_hint(speaker_source=speaker_source)
            _runtime.LOGGER.info(
                "Transcription started with technical modes=%s rules=%s",
                list(active_modes),
                self._it_mode_term_count(),
            )


def main():
    _runtime.LOGGER.info("Entering top wrapper main()")
    root = _runtime.tk.Tk()
    OperatorAssistApp(root)
    _runtime.LOGGER.info("Top wrapper GUI mainloop starting")
    root.mainloop()
    _runtime.LOGGER.info("Top wrapper GUI loop finished")


if __name__ == "__main__":
    main()
