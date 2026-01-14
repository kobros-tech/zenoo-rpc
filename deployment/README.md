# Zenoo RPC Deployment Guide

Production deployment configurations for Zenoo RPC HTTP Server on Kubernetes.

## Overview

This directory contains production-ready deployment files for running Zenoo RPC as an HTTP REST API server. The server provides 8 powerful tools for Odoo operations accessible via standard HTTP/JSON.

## Deployment Options

### HTTP Server Mode (Recommended for Production)

The HTTP server provides a REST API that works with any HTTP client (AI agents, applications, curl, etc.).

**Features:**
- Standard REST API with Bearer token authentication
- Works with any HTTP client in any language
- Production-ready with health checks and metrics
- Horizontal scaling with Kubernetes HPA
- Redis caching support

### Transport Modes

You can configure the server to use different transports via the `MCP_TRANSPORT_TYPE` environment variable:

1. **`http`** (Default) - HTTP REST API server
   - Best for: Production deployments, AI agents, custom applications
   - Port: 8000 (configurable)
   - Authentication: Bearer token

2. **`stdio`** - Standard input/output communication
   - Best for: Claude Desktop integration, local development
   - Used internally by the HTTP proxy

## Quick Start

### 1. Prerequisites

- Kubernetes cluster (1.21+)
- kubectl configured
- Access to Odoo instance
- Docker registry (for custom images)

### 2. Create Secrets

```bash
# Create namespace
kubectl create namespace zenoo-production

# Create MCP API key secret
kubectl create secret generic mcp-secret \
  -n zenoo-production \
  --from-literal=api-keys=$(openssl rand -base64 32)

# Create Odoo connection secret
kubectl create secret generic odoo-secret \
  -n zenoo-production \
  --from-literal=url=https://your-odoo-instance.com \
  --from-literal=database=your_database \
  --from-literal=username=admin \
  --from-literal=password=your_password
```

### 3. Deploy

```bash
# Apply all configurations
kubectl apply -f deployment/k8s/zenoo-rpc-deployment.yaml

# Check deployment status
kubectl get pods -n zenoo-production -l app=zenoo-rpc

# Check logs
kubectl logs -n zenoo-production -l app=zenoo-rpc --tail=50 -f
```

### 4. Test the Deployment

```bash
# Port forward to test locally
kubectl port-forward -n zenoo-production svc/zenoo-rpc-service 8000:80

# List available tools
curl http://localhost:8000/tools \
  -H "Authorization: Bearer $(kubectl get secret mcp-secret -n zenoo-production -o jsonpath='{.data.api-keys}' | base64 -d)"

# Test a search
curl -X POST http://localhost:8000/tools/search_records \
  -H "Authorization: Bearer $(kubectl get secret mcp-secret -n zenoo-production -o jsonpath='{.data.api-keys}' | base64 -d)" \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"model": "res.partner", "limit": 5}}'
```

## Configuration

### Environment Variables

All configuration is done via environment variables:

#### MCP HTTP Server
- `MCP_PORT` - Server port (default: 8000)
- `MCP_HOST` - Bind address (default: 0.0.0.0)
- `MCP_API_KEYS` - Bearer token for authentication (required)
- `MCP_TRANSPORT_TYPE` - Transport mode: "http" or "stdio" (default: http)

#### Odoo Connection
- `ODOO_URL` - Odoo server URL (required)
- `ODOO_DATABASE` - Database name (required)
- `ODOO_USERNAME` - Odoo username (required)
- `ODOO_PASSWORD` - Odoo password (required)

#### Performance
- `WORKERS` - Number of workers (default: 4)
- `MAX_CONNECTIONS` - Max connections (default: 20)
- `LOG_LEVEL` - Log level: DEBUG, INFO, WARNING, ERROR (default: INFO)

#### Optional: Redis Cache
- `REDIS_URL` - Redis connection URL
- `CACHE_BACKEND` - Cache backend: "memory" or "redis" (default: memory)

### Secrets Management

Secrets are stored in Kubernetes Secrets:

**mcp-secret**: MCP API keys
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mcp-secret
  namespace: zenoo-production
type: Opaque
stringData:
  api-keys: "your-secret-key-here"
```

**odoo-secret**: Odoo connection credentials
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: odoo-secret
  namespace: zenoo-production
type: Opaque
stringData:
  url: "https://your-odoo-instance.com"
  database: "your_database"
  username: "admin"
  password: "your_password"
```

## Architecture

### Components

1. **Deployment** (`zenoo-rpc-deployment.yaml`)
   - 3 replicas (configurable)
   - Rolling update strategy
   - Health checks and probes
   - Resource limits

2. **Service** (`zenoo-rpc-service`)
   - ClusterIP type
   - Port 80 → 8000
   - Load balancing

3. **Ingress** (optional)
   - NGINX ingress controller
   - SSL/TLS termination
   - Rate limiting

4. **HorizontalPodAutoscaler**
   - Min replicas: 3
   - Max replicas: 10
   - CPU target: 70%
   - Memory target: 80%

5. **PodDisruptionBudget**
   - MinAvailable: 2
   - Ensures availability during updates

### Deployment Flow

```
Internet/AI Agent → Ingress → Service → Pod (HTTP Server) → Odoo
                      ↓
                   LoadBalancer
                      ↓
              Multiple Replicas
```

## Scaling

### Horizontal Scaling

The HPA automatically scales based on CPU and memory:

```bash
# View HPA status
kubectl get hpa -n zenoo-production

# Manually scale (HPA will override)
kubectl scale deployment zenoo-rpc -n zenoo-production --replicas=5
```

### Vertical Scaling

Adjust resource limits in deployment:

```yaml
resources:
  requests:
    memory: "1Gi"    # Increase from 512Mi
    cpu: "500m"      # Increase from 250m
  limits:
    memory: "2Gi"    # Increase from 1Gi
    cpu: "2000m"     # Increase from 1000m
```

## Monitoring

### Health Checks

- **Liveness**: `/health` - Container is alive
- **Readiness**: `/ready` - Container can serve traffic
- **Startup**: `/health` - Initial startup check

### Metrics (if enabled)

```bash
# View metrics endpoint
kubectl port-forward -n zenoo-production svc/zenoo-rpc-service 8000:80
curl http://localhost:8000/metrics
```

### Logs

```bash
# Stream logs from all pods
kubectl logs -n zenoo-production -l app=zenoo-rpc -f

# Logs from specific pod
kubectl logs -n zenoo-production <pod-name> -f

# Previous pod logs (if crashed)
kubectl logs -n zenoo-production <pod-name> --previous
```

## Troubleshooting

### Pod Not Starting

```bash
# Check pod status
kubectl describe pod -n zenoo-production <pod-name>

# Check events
kubectl get events -n zenoo-production --sort-by='.lastTimestamp'

# Check secrets
kubectl get secret mcp-secret -n zenoo-production -o yaml
kubectl get secret odoo-secret -n zenoo-production -o yaml
```

### Connection Issues

```bash
# Test Odoo connection from pod
kubectl exec -it -n zenoo-production <pod-name> -- curl -I $ODOO_URL

# Check DNS resolution
kubectl exec -it -n zenoo-production <pod-name> -- nslookup your-odoo-instance.com

# Test Redis connection (if using)
kubectl exec -it -n zenoo-production <pod-name> -- redis-cli -h redis-service ping
```

### Authentication Errors

```bash
# Verify MCP API key
kubectl get secret mcp-secret -n zenoo-production -o jsonpath='{.data.api-keys}' | base64 -d

# Test with correct key
curl -H "Authorization: Bearer YOUR_KEY" http://localhost:8000/tools
```

## Security

### Best Practices

1. **Use Secrets**: Never hardcode credentials
2. **Network Policies**: Restrict pod-to-pod communication
3. **RBAC**: Limit service account permissions
4. **TLS**: Enable SSL/TLS on ingress
5. **API Keys**: Rotate regularly
6. **Security Context**: Run as non-root user
7. **Read-Only Root**: Filesystem is read-only

### Network Policy (Optional)

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: zenoo-rpc-netpol
  namespace: zenoo-production
spec:
  podSelector:
    matchLabels:
      app: zenoo-rpc
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: ingress-nginx
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - podSelector: {}
    ports:
    - protocol: TCP
      port: 6379  # Redis
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 443  # Odoo HTTPS
```

## Backup and Disaster Recovery

### Configuration Backup

```bash
# Export all resources
kubectl get all,secrets,configmaps,ingress -n zenoo-production -o yaml > backup.yaml

# Restore
kubectl apply -f backup.yaml
```

### Database Backups

Zenoo RPC is stateless - Odoo holds the data. Backup Odoo separately.

## Updates and Rollbacks

### Rolling Update

```bash
# Update image
kubectl set image deployment/zenoo-rpc \
  -n zenoo-production \
  zenoo-rpc=zenoo-rpc:1.1.0

# Watch rollout
kubectl rollout status deployment/zenoo-rpc -n zenoo-production
```

### Rollback

```bash
# Rollback to previous version
kubectl rollout undo deployment/zenoo-rpc -n zenoo-production

# Rollback to specific revision
kubectl rollout undo deployment/zenoo-rpc -n zenoo-production --to-revision=2

# View rollout history
kubectl rollout history deployment/zenoo-rpc -n zenoo-production
```

## Performance Tuning

### Connection Pooling

Adjust `MAX_CONNECTIONS` based on your Odoo server capacity:

```yaml
env:
- name: MAX_CONNECTIONS
  value: "50"  # Increase for high traffic
```

### Worker Processes

Adjust `WORKERS` based on CPU cores:

```yaml
env:
- name: WORKERS
  value: "8"  # 2x CPU cores recommended
```

### Redis Caching

Enable Redis for better performance:

```yaml
env:
- name: CACHE_BACKEND
  value: "redis"
- name: REDIS_URL
  value: "redis://redis-service:6379/0"
```

## Support

- Documentation: [HTTP-SERVER.md](../docs/HTTP-SERVER.md)
- Issues: GitHub Issues
- Logs: `kubectl logs -n zenoo-production -l app=zenoo-rpc`
