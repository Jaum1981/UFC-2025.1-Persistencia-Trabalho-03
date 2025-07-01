# UFC-2025.1-Persistencia-Trabalho-03 - Relatório de Divisão de Atividades

**Projeto:** Cinema API – Gerenciamento de Filmes, Diretores, Sessões, Salas, Ingressos e Pagamentos com FastAPI  
**Disciplina:** Desenvolvimento de Software para Persistência  
**Data de entrega:** 01.07.2025  
**Dupla:**

* **Aluno 1:** João Victor Amarante Diniz (510466)
* **Aluno 2:** Francisco Breno da Silveira (511429)

### 1. Atividades Executadas

1. **Modelagem de Entidades e Relacionamentos**

   * Models: `Movie`, `Director`, `Room`, `Session`, `Ticket`, `PaymentDetails`
   * Relacionamentos 1\:N e N\:N implementados via `Relationship` e tabelas de link.
   * **Responsável: João Victor Amarante Diniz (510466)**

2. **DTOs e Validações (Pydantic)**

   * Criação e Update DTOs para todas as entidades
   * Validações de formato (datas, URLs), conflitos de ID, imutabilidade de IDs no PUT.
   * **Responsáveis:  Francisco Breno da Silveira (511429) e João Victor Amarante Diniz (510466)**

3. **Endpoints CRUD & Auxiliares**

   * **F1–F3**: CRUD completo em `/movies`, `/directors`, `/rooms`, `/sessions`, `/tickets`, `/payments`
   * **F4**: `/count` para cada entidade
   * **F5**: paginação em rotas `/filter` e `PaginationMeta`
   * **F6**: filtros por atributos (e.g. `?genre=…`, `?after=…`, `?min_price=…`)
   * Divisão de responsabilidade:
      * **Francisco Breno da Silveira (511429)** - Responsável por implementar F1 - F6 para `Directors`, `/movies`,`/rooms`.
      * **João Victor Amarante Diniz (510466)** - Responsável por implementar F1 - F6 para as demais entidades.


4. **F7**: Consultas Avançados

   * `GET /complex-queries/cinema-revenue-report`: Consulta complexa que retorna relatório de faturamento do cinema Envolve 5 coleções: Sessions, Movies, Directors, Rooms, Tickets, Payments
      * **Responsável: João Victor Amarante Diniz (510466)**
   * `GET /complex-queries/director-performance-analysis`: Consulta complexa que analisa a performance dos diretores Envolve 6 coleções: Directors, Movies, Sessions, Rooms, Tickets, Payments
      * **Responsável: Francisco Breno da Silveira (511429)**