# 🛫 Projeto BD – Entrega 2 (2024/2025)

**Desenvolvimento em SQL, API REST, OLAP e Otimização de Consultas**

---

## 📌 Sobre o Projeto

Este repositório contém a **Entrega 2 do Projeto da unidade curricular Bases de Dados** do curso de Engenharia Informática e de Computadores (IST), ano letivo **2024/2025**.  
O objetivo desta fase é **implementar, analisar e otimizar uma base de dados relacional**, com foco em:

- **Implementação de Restrições de Integridade**
- **Preenchimento massivo da Base de Dados**
- **Desenvolvimento de uma API RESTful para gestão de bilhetes**
- **Criação de Vistas Materializadas para análise OLAP**
- **Consultas SQL analíticas e índices para otimização**

---

## 🎯 Objetivos do Trabalho

1. **Criar e configurar a base de dados Aviacao** no PostgreSQL, usando o esquema fornecido.
2. **Definir e implementar Restrições de Integridade** (com triggers quando necessário).
3. **Popular a base de dados** com dados consistentes e volumosos.
4. **Desenvolver uma aplicação RESTful** para gestão de bilhetes.
5. **Criar vistas materializadas e consultas OLAP** para análise de dados.
6. **Aplicar índices e justificar otimizações de desempenho**.

---

## 🛠 O que foi feito

- **Base de dados criada** com o esquema oficial fornecido (Anexo A do enunciado).
- **Triggers e constraints** para garantir integridade:
  - **RI-1**: Classe do bilhete = classe do assento + avião correto no check-in.
  - **RI-2**: Limite de bilhetes por classe = capacidade do avião.
  - **RI-3**: Hora da venda anterior à hora da partida dos voos associados.
- **Preenchimento massivo**:
  - ≥10 aeroportos internacionais reais (Europa).
  - ≥10 aviões de ≥3 modelos reais (com assentos realistas e 10% para 1ª classe).
  - ≥5 voos/dia entre 01/01/2025 e 31/07/2025 cobrindo todos os aeroportos e aviões.
  - ≥30.000 bilhetes vendidos e ≥10.000 vendas, com check-in para voos já realizados.
- **API RESTful** para acesso programático (JSON), implementando endpoints:
  - `/` → lista aeroportos (nome e cidade).
  - `/voos/<partida>/` → lista voos a partir do aeroporto nas próximas 12h.
  - `/voos/<partida>/<chegada>/` → próximos 3 voos com bilhetes disponíveis.
  - `/compra/<voo>/` → compra de bilhetes (transação segura, sem SQL injection).
  - `/checkin/<bilhete>/` → check-in automático com atribuição de assento.
- **Vista materializada** `estatisticas_voos` para análise OLAP:
  - Combina info de voos, aeroportos, assentos, vendas e bilhetes.
  - Inclui métricas como nº passageiros por classe, vendas totais, ocupação, dimensões de tempo.
- **Consultas OLAP e SQL avançadas**:
  - Rotas com maior procura (preenchimento médio).
  - Rotas cobertas por todos os aviões nos últimos 3 meses.
  - Rentabilidade por dimensões espaço e tempo.
  - Padrões de classes por dia da semana e drill down por localização.
- **Índices criados** sobre a vista para otimização coletiva das consultas, com **justificação teórica** e análise com `EXPLAIN ANALYSE`.

---

## 📂 Estrutura do Repositório

```
.
├── app/                         # Código da API REST (Python + Flask)
│   ├── app.py                   # Ficheiro principal da aplicação
│   ├── requirements.txt         # Dependências
|
├── data/                        # Scripts e ficheiros para preenchimento da BD
│   ├── aviacao.sql              # Inserção de dados via INSERT
│   ├── gerar_populate.py        # Script Python para gerar de forma massiva os dados
|
├── BD2425P2.ipynb               # Notebook com respostas às secções 1, 4, 5 e 6
├── enunciado-BD2425P2.pdf       # Enunciado oficial
└── README.md                    # Este ficheiro
```

---

## ✅ Funcionalidades Implementadas

### **1. Restrições de Integridade**

- Implementação em **SQL** e **triggers** para:
  - Correspondência entre classe de bilhete e assento no check-in.
  - Limitação da venda de bilhetes por classe à capacidade do avião.
  - Garantia de vendas realizadas antes da hora de partida.

### **2. Preenchimento da Base de Dados**

- Cobertura garantida:
  - Todos os aeroportos usados em voos.
  - Aviões escalados de forma consistente (voos de ida e volta).
  - Check-in realizado para voos passados.

### **3. API RESTful**

- Segurança: prevenção de **SQL Injection** (parametrização de queries).
- Atomicidade: uso de **transações** para operações críticas (`compra` e `checkin`).
- **JSON estruturado** e códigos HTTP adequados (200, 400, 404, 500).

### **4. Vista estatisticas_voos**

- Esquema:

```
(no_serie, hora_partida, cidade_partida, pais_partida,
 cidade_chegada, pais_chegada, ano, mes, dia_do_mes, dia_da_semana,
 passageiros_1c, passageiros_2c, assentos_1c, assentos_2c,
 vendas_1c, vendas_2c)
```

### **5. Consultas OLAP**

- **Rotas mais procuradas** pelo rácio ocupação/capacidade.
- **Rotas cobertas por toda a frota** nos últimos 3 meses.
- **Rentabilidade global e drill-down** (por país, cidade, tempo).
- **Padrão por dia da semana** no rácio 1ª vs. 2ª classe.

### **6. Índices**

- Índices criados sobre colunas de filtragem frequente na vista (`aeroporto`, `hora_partida`, `rotas`).
- Justificação com análise de custo antes/depois via `EXPLAIN ANALYSE`.

---

## 🔍 Ferramentas Utilizadas

- **PostgreSQL** (modelação, triggers, queries OLAP).
- **Python + Flask** (API RESTful).
- **Docker** (ambiente para execução da app e BD).
- **Script Python** (geração de dados para populate).
- **Jupyter Notebook** (análise e documentação).
