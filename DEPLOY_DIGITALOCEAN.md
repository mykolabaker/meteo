# Deploying to DigitalOcean Kubernetes (DOKS)

## Prerequisites

1. [DigitalOcean account](https://www.digitalocean.com/) - includes $200 free credit for 60 days
2. [doctl CLI](https://docs.digitalocean.com/reference/doctl/how-to/install/)
3. [kubectl](https://kubernetes.io/docs/tasks/tools/)
4. [Docker](https://www.docker.com/)

## Step 1: Install and Configure doctl

```bash
# macOS
brew install doctl

# Linux (snap)
sudo snap install doctl

# Linux (manual)
cd ~
wget https://github.com/digitalocean/doctl/releases/download/v1.104.0/doctl-1.104.0-linux-amd64.tar.gz
tar xf doctl-1.104.0-linux-amd64.tar.gz
sudo mv doctl /usr/local/bin

# Authenticate (creates token at https://cloud.digitalocean.com/account/api/tokens)
doctl auth init
```

## Step 2: Create Kubernetes Cluster

```bash
# List available regions
doctl kubernetes options regions

# List available node sizes
doctl kubernetes options sizes

# Create cluster (takes ~4-5 minutes)
doctl kubernetes cluster create meteo-cluster \
  --region ams3 \
  --size s-1vcpu-2gb \
  --count 2 \
  --wait

# This automatically saves kubeconfig. Verify:
kubectl get nodes
```

**Cluster cost**: ~$12/month per node (s-1vcpu-2gb)

## Step 3: Set Up Container Registry

DigitalOcean has a built-in container registry.

```bash
# Create registry (starter tier is free for 500MB)
doctl registry create meteo-registry

# Login to registry
doctl registry login

# Get registry endpoint
doctl registry get

# Build and push
docker build -t registry.digitalocean.com/meteo-registry/meteo-proxy:latest .
docker push registry.digitalocean.com/meteo-registry/meteo-proxy:latest

# Allow cluster to pull from registry
doctl kubernetes cluster registry add meteo-cluster
```

## Step 4: Update Deployment Image

Edit `k8s/deployment.yaml` and update the image:

```yaml
# Change this line:
image: meteo-proxy:latest

# To:
image: registry.digitalocean.com/meteo-registry/meteo-proxy:latest
```

Also change `imagePullPolicy`:

```yaml
imagePullPolicy: Always
```

## Step 5: Install NGINX Ingress Controller

```bash
# Install via DigitalOcean 1-Click (recommended)
doctl kubernetes 1-click install meteo-cluster --1-clicks ingress-nginx

# Or via Helm
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --set controller.publishService.enabled=true

# Wait for Load Balancer IP
kubectl get svc -n ingress-nginx ingress-nginx-controller -w
```

## Step 6: Deploy Application

```bash
# Apply all Kubernetes manifests
kubectl apply -f k8s/

# Watch deployment progress
kubectl get pods -w

# Check all resources
kubectl get all -l app=meteo-proxy
```

## Step 7: Access Your Application

### Get External IP

```bash
# Get the Load Balancer IP
kubectl get svc -n ingress-nginx ingress-nginx-controller

# Or check ingress directly
kubectl get ingress meteo-proxy
```

### Test the API

```bash
# Replace with your actual IP
export API_URL="http://YOUR_LOAD_BALANCER_IP"

# Health check
curl $API_URL/health/live

# Weather endpoint
curl "$API_URL/api/v1/weather?lat=52.52&lon=13.41"

# Metrics
curl $API_URL/metrics

# API docs
open $API_URL/docs
```

## Step 8: (Optional) Add Custom Domain + TLS

### Install cert-manager

```bash
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.14.0/cert-manager.yaml

# Wait for it to be ready
kubectl wait --for=condition=Available deployment --all -n cert-manager --timeout=120s
```

### Create ClusterIssuer

```bash
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: your-email@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
      - http01:
          ingress:
            class: nginx
EOF
```

### Update Ingress with TLS

Replace `k8s/ingress.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: meteo-proxy
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
    - hosts:
        - meteo.yourdomain.com
      secretName: meteo-tls
  rules:
    - host: meteo.yourdomain.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: meteo-proxy
                port:
                  number: 80
```

Point your domain's A record to the Load Balancer IP.

## Useful Commands

```bash
# View logs
kubectl logs -l app=meteo-proxy -f

# Describe pod (debugging)
kubectl describe pod -l app=meteo-proxy

# Scale manually
kubectl scale deployment meteo-proxy --replicas=3

# Check HPA status
kubectl get hpa meteo-proxy

# Port forward for local testing
kubectl port-forward svc/meteo-proxy 8080:80

# Restart deployment
kubectl rollout restart deployment meteo-proxy

# View rollout status
kubectl rollout status deployment meteo-proxy

# Update to new image
docker build -t registry.digitalocean.com/meteo-registry/meteo-proxy:v2 .
docker push registry.digitalocean.com/meteo-registry/meteo-proxy:v2
kubectl set image deployment/meteo-proxy meteo-proxy=registry.digitalocean.com/meteo-registry/meteo-proxy:v2
```

## Cleanup

```bash
# Delete all resources
kubectl delete -f k8s/

# Delete the cluster
doctl kubernetes cluster delete meteo-cluster

# Delete the registry (optional)
doctl registry delete
```

## Cost Summary

| Resource | Monthly Cost |
|----------|-------------|
| 2x s-1vcpu-2gb nodes | ~$24 |
| Load Balancer | ~$12 |
| Container Registry (starter) | Free (500MB) |
| **Total** | **~$36/month** |

Free tier: $200 credit for 60 days for new accounts.

## DigitalOcean Dashboard

You can also manage everything via the web UI:
- Kubernetes: https://cloud.digitalocean.com/kubernetes
- Container Registry: https://cloud.digitalocean.com/registry
- Load Balancers: https://cloud.digitalocean.com/networking/load_balancers
