# Diretrizes do Projeto: Kendo RPG Status

## Visão Geral
Este é um mini site de incentivo à educação física com temática de RPG, focado em treinos de Kendo e Musculação, dividido por níveis e cronogramas de missões.

## Stack Tecnológica
- **Backend:** Python com FastAPI, SQLite e SQLAlchemy.
- **Autenticação:** JWT (JSON Web Tokens) usando `PyJWT` e `passlib`.
- **Frontend:** HTML5, CSS3 puro (com tema totalmente escuro, fundo preto puro `#000000` e fontes monoespçadas) e JavaScript moderno (Vanilla JS).
- **Estilo de Código:** Sem emojis, minimalista, limpo e direto.

## Regras de Desenvolvimento para o Copilot
1. **Tema Visual:** Manter sempre o fundo preto (`#000000`), bordas cinzas simples e texto branco, preservando a estética de terminal/RPG retrô. NUNCA adicione fundos claros ou emojis nas respostas ou no design.
2. **Escopo Modular:** Ao sugerir novas funcionalidades (como salvamento de missões, banco de dados de níveis ou sistema de XP), mantenha a separação clara entre as rotas do FastAPI (`main.py`) e a interface do usuário (`index.html`).
3. **Segurança:** Rotas protegidas no FastAPI devem validar o token JWT enviado pelo frontend no header `Authorization: Bearer <token>`.