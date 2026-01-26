# Medical Product Chatbot API

A production-ready FastAPI backend that provides intelligent medical product recommendations using Groq LLM and MongoDB. Deployed on Vercel for serverless scalability.

## 🎯 Features

- **Conversational AI**: Natural language product recommendations using Groq's Qwen 2.5 32B and Llama 3.3 70B models
- **Smart Filtering**: Multi-criteria product search (category, medical features, tags, nutritional info)
- **In-Memory Caching**: Optimized performance with LRU cache and data preloading
- **RESTful API**: Clean endpoints for chat, reset, and health checks
- **CORS Enabled**: Ready for frontend integration
- **Serverless Deployment**: Zero-config Vercel deployment

## 🏗️ Architecture

User Query → FastAPI → Groq LLM (Intent Detection) → MongoDB Filter → Groq LLM (Response Generation) → User


**Two-Stage Processing:**
1. **Stage 1**: Extract search criteria (category, medical features, tags)
2. **Stage 2**: Generate personalized recommendations with product links and pricing

## 📦 Tech Stack

- **Framework**: FastAPI 
- **Database**: MongoDB Atlas
- **LLM Provider**: Groq (Qwen 2.5 32B, Llama 3.3 70B)
- **Deployment**: Vercel
- **Language**: Python 3.9+

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- MongoDB Atlas account
- Groq API key

### Local Development

**Clone the repository**
```bash
git clone https://github.com/karrrtik-2/medical-product-chatbot-api.git
cd medical-product-chatbot-api
```

**Run the server**

```bash
uvicorn app:app --reload
```
