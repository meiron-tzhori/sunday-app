# Sunday Application

A simple stateful REST API application deployed on Kubernetes.

The application allows users to store grocery product quantities and retrieve aggregated product amounts.
It demonstrates correct Kubernetes deployment behavior, persistent storage handling, and lifecycle management.

All examples assume the namespace:

```
ep-test
```

---

# Overview

The Sunday Application is a lightweight REST API service that:

* Stores product quantities per user
* Aggregates product totals across users
* Persists data using Kubernetes PersistentVolumeClaim
* Survives pod restarts and rollout events

The purpose of this component is to demonstrate:

* Application-level design inside Kubernetes
* Correct PVC usage
* Deployment lifecycle handling
* Persistent data across pod recreation

---

# Architecture

The system consists of:

* **Python-based REST API**
* **SQLite database file stored on the mounted volume (PVC)**
* **Single-replica Deployment**
* **PersistentVolumeClaim**
* **Kubernetes Service**

### Storage Model (SQLite on PVC)

The application persists state using an embedded **SQLite** database.
The SQLite database file is stored on the directory that is mounted from the **PersistentVolumeClaim**, so the data survives pod deletion, restarts, and deployment rollouts.

---

### Architectural Principles

1. **Simplicity**
   The logic is intentionally minimal to focus on Kubernetes behavior rather than framework complexity.

2. **File-Based Persistence**
   Data is stored on a mounted volume backed by a PersistentVolumeClaim.

3. **Single Replica**
   The application runs as a single replica to avoid write conflicts and concurrency issues.

4. **Stateless Container + Stateful Volume**
   The container itself is stateless.
   Persistence is achieved only through the mounted volume.

---

# Project Structure

```
sunday-app/
├── app/
│   └── main.py
├── Dockerfile
├── k8s/
│   ├── deployment.yaml
│   ├── pvc.yaml
│   └── service.yaml
└── requirements.txt
```

---

# Prerequisites

* Kubernetes cluster
* kubectl
* Docker
* Namespace `ep-test`

Create namespace if needed:

```bash
kubectl create namespace ep-test || true
```

---

# Build & Deployment

## 1. Build Docker Image

From the sunday-app directory:

```bash
cd sunday-app
docker build -t sunday-app:latest .
```

If your cluster pulls images from a registry:

```bash
docker tag sunday-app:latest <your-registry>/sunday-app:latest
docker push <your-registry>/sunday-app:latest
```

Update `deployment.yaml` accordingly if using a registry image.

---

## 2. Deploy to Kubernetes

Apply all manifests:

```bash
kubectl apply -n ep-test -f k8s/
```

Verify:

```bash
kubectl get pods -n ep-test
kubectl get pvc -n ep-test
kubectl get svc -n ep-test
```

Expected:

* Pod in Running state
* PVC Bound
* Service created

---

# Accessing the Application

The application is exposed via a Kubernetes Service (`k8s/service.yaml`).
The access method depends on the Service type defined in the manifest.

---

## Option 1 – ClusterIP (Port Forward)

```bash
kubectl -n ep-test port-forward svc/sunday-app 8080:80
```

Access via:

```
http://localhost:8080
```

---

## Option 2 – NodePort

```bash
kubectl get svc sunday-app -n ep-test
```

Access via:

```
http://<node-ip>:<node-port>
```

---

## Option 3 – LoadBalancer

```bash
kubectl get svc sunday-app -n ep-test
```

Access via:

```
http://<external-ip>
```

---

# API Behavior

After deploying the application, perform the following flow:

1. Add products for different users.
2. Query aggregated totals.
3. Delete a product for a specific user.
4. Restart the pod / rollout the deployment.
5. Verify that the data remains consistent.

This validates both business logic and persistence behavior.

---

## 1. Add / Update Product for User

Add a product quantity for a specific user:

```bash
curl -X POST "http://localhost:8080/add_product" \
  -H "Content-Type: application/json" \
  -d '{
        "user_id": "user1",
        "product_name": "banana",
        "amount": 5
      }'
```

Add from another user:

```bash
curl -X POST "http://localhost:8080/add_product" \
  -H "Content-Type: application/json" \
  -d '{
        "user_id": "user2",
        "product_name": "banana",
        "amount": 5
      }'
```

If the same user adds the same product again, the quantity is updated according to the application logic.

---

## 2. Get Aggregated Product Total

Retrieve total quantity across all users:

```bash
curl "http://localhost:8080/get_product_amount?product_name=banana"
```

Example response:

```json
{
  "ok": true,
  "data": {
    "product_name": "banana",
    "total_amount": 10,
    "users_count": 2
  }
}
```

This confirms:

* Total quantity across users
* Number of users contributing

---

## 3. Delete Product for a Specific User

Users can delete a product entry that belongs to them.

```bash
curl -X DELETE "http://localhost:8080/delete_product" \
  -H "Content-Type: application/json" \
  -d '{
        "user_id": "user1",
        "product_name": "banana"
      }'
```

After deletion:

```bash
curl "http://localhost:8080/get_product_amount?product_name=banana"
```

Expected:

* `total_amount` decreases accordingly
* `users_count` updates if that user no longer contributes

---

## 4. Persistence Verification

After inserting data:

```bash
kubectl rollout restart deployment/sunday-app -n ep-test
kubectl rollout status deployment/sunday-app -n ep-test
```

Re-run:

```bash
curl "http://localhost:8080/get_product_amount?product_name=banana"
```

Expected:

* Data remains intact
* Values match state before restart

---

# Testing Scenarios

## 1. Basic Functionality

* Add products for multiple users
* Retrieve aggregated totals
* Delete product for a specific user
* Validate updated totals

---

## 2. Pod Restart (Self-Healing)

```bash
kubectl delete pod -n ep-test <pod-name>
```

Expected:

* Pod is recreated automatically
* Data remains intact

---

## 3. Rollout Restart

```bash
kubectl rollout restart deployment/sunday-app -n ep-test
```

Expected:

* New pod created
* Persistent data preserved

---

## 4. PVC Validation

```bash
kubectl get pvc -n ep-test
kubectl describe pvc <pvc-name> -n ep-test
```

Expected:

* PVC remains Bound
* No data loss across restarts

---

# Design Decisions

### Why Python?

* Rapid implementation
* Minimal boilerplate
* Clear readable logic

### Why File-Based Storage?

* Simpler than integrating a database
* Focus remains on Kubernetes persistence
* Avoids external dependencies

### Why Using `user_id` Explicitly?

The schema intentionally uses `user_id` rather than implicit user handling.
This simplifies aggregation logic and keeps the data model aligned with the assignment requirements.

### Why Single Replica?

* Avoids concurrency handling complexity
* Ensures deterministic behavior
* Keeps scope aligned with assignment goals

---

# Assumptions

* No authentication layer required
* Single replica only
* No concurrent write protection
* Data format is simple JSON-based storage

---

# Limitations

* Not production-grade
* No horizontal scaling
* No database
* No health probes beyond basic container lifecycle
* No resource limits tuning

---
