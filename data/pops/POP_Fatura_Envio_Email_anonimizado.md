# POP – Fatura: Não Recebimento / Envio por E-mail
### [Versão anonimizada/pseudonimizada — documento avulso da série]

> **Nota metodológica:** mesma metodologia e pseudônimos dos POPs anteriores. Dois sistemas novos neste documento (COC → SISCAD; RAO → SISNEG); dois endereços de e-mail reais foram substituídos; o número de WhatsApp institucional foi omitido, como nos demais documentos. As rotinas 56658 (Token), 1181 e 1357 já constavam na chave (50148, 50182 e 50149) — mantidos os mesmos códigos. Uma frase do original ficou incompleta (sem número de rotina) — preservei a lacuna e anotei na chave.

## Primeiro processo: autenticação por Token

**Procedimento de Segurança:**
- Se o cliente **está** autenticado pela URA, prossiga o atendimento pelos itens abaixo.
- Se **não está** autenticado, realize o envio de Token conforme rotina 50148.
- Se o Token for validado, prossiga o atendimento.
- Se não for possível confirmar pelo Token, **NÃO** envie a fatura nem altere a forma de envio pelos procedimentos abaixo — informe que as faturas podem ser vistas no autoatendimento (canais da rotina 50182).
- Se o cliente questionar informações sobre a fatura (lançamentos, valores, vencimento, limite disponível), siga a rotina 50149.

## 1.1. Reenvio de fatura por e-mail

Exclusivo para clientes PF. Clientes PJ devem emitir a fatura conforme item "c" abaixo e aderir à emissão definitiva por e-mail (item 1.2.c). Podem ser enviadas, num único contato, todas as faturas de cartões de modalidades diferentes do cliente.

**b) Quadro Contratado — somente envio da fatura atual:**
- Acesse o aplicativo cartão `17.01.01` + dados do cliente; escolha a conta cartão para o reenvio; na tela de cadastro, tecle "Enter"; acesse o item 17 — Reenvio Fatura; peça o e-mail que o cliente quer usar e confira se é o cadastrado.
- **Opção A** (envio ao e-mail já cadastrado no sistema): cliente pode estar autenticado OU validado por Token.
- **Opção B:** mesmo com o cliente autenticado, é **obrigatória** a validação por Token. Se validado, ofereça cadastrar ou atualizar o e-mail; se o cliente aceitar, siga o item 1.3.
- Se não for possível validar por Token, oriente o cliente a obter a fatura pelos canais da rotina 50182.
- Informe e confirme a conta cartão (modalidade e bandeira); confirme o procedimento. A fatura chega em até 2 minutos, em PDF. O título do e-mail é "Segunda Via Fatura"; remetente: um dos endereços institucionais de envio de fatura; a senha para abrir o PDF são os 5 primeiros dígitos do CPF do cliente.
  - Oriente o cliente a observar a caixa de spam e marcar o remetente como confiável/seguro. Se ele quiser outro e-mail, use a "Opção B" e, no campo "Outro", insira o e-mail informado.
  - Ofereça a mudança da forma de envio para emissão (definitiva) por e-mail — se aceitar, siga o item 1.2.
- **c) Cliente PJ:** a fatura de cartões PJ e o demonstrativo mensal podem ser consultados no Alfa Digital PJ (Cartão > Consolidado Empresa > Acesso de usuário ao Centro de Custo) ou no App Alfa PJ, pelo representante autorizado do Centro de Custo ou por usuário com acesso concedido pelo Administrador de Segurança.

Se o cliente quiser mudar a forma de envio, siga para o item 1.2.

## 1.2. Mudança da forma de envio (Quadro Contratado)

- Acesse o aplicativo cartão `17.01.01` + dados do cliente; escolha a conta cartão (procedimento individual por conta); acesse os itens `04.41.19` — Emissão de Extrato; observe a situação "Atual" e mude para "COM emissão de extrato via e-mail".
- O comando gera um duplo sim; o cliente deve confirmar em até 7 dias, pelos canais:
  - **Correntista:** App Alfa, AAPF (área logada) — Internet e TAA.
  - **Não correntista:** AAPF (área logada) — Internet e TAA.

> **Atenção:** se, no comando de alteração, o sistema informar "Cliente não está habilitado para receber e-mail", habilite-o: acesse no SISALFA o aplicativo `SISCAD 06.11` + dados do cliente; na linha 0006 E-mail, altere os três campos de "N" para "S" e confirme, alertando o cliente de que esse ajuste autoriza o banco a enviar outras comunicações por e-mail (ex.: promoções).

O envio por e-mail passa a valer a partir da próxima fatura a fechar (status "A faturar").

- **Cliente PJ:** oriente a inibir a emissão da fatura pelo Alfa Digital PJ, via internet ou celular.

## 1.3. Atualização de e-mail (PF)

- Faça a autenticação por Token, conforme rotina 50148:
  - **Se sucesso**, prossiga o atendimento.
  - **Se não houver sucesso**, oriente o cliente sobre os canais disponíveis para atualizar o e-mail.
- Se o cliente não tem e-mail cadastrado, ou precisa alterá-lo: o SAC Quadro Próprio, o QC Especializado Cartão, o QC SAC Generalista e a Bancada Portador podem atualizar o e-mail no SISALFA, aplicativo cartão `17.01.01.04.41.18` (não gera duplo sim).
- Oriente sobre os canais disponíveis para atualizar o e-mail, presentes na rotina 50220 (Atualização Cadastral), item 3: site institucional e App Alfa; App Alfa; Plataforma de Relacionamento; agências.
- Se o cliente for PJ, oriente sobre os canais da mesma rotina 50220, item 4: Alfa Digital PJ.

## Item 2 — Inibição da fatura impressa

Incentive o cliente a aderir à fatura por e-mail, destacando:
- **Agilidade** — a fatura chega mais rápido, no mesmo leiaute da impressa;
- **Sustentabilidade** — evita a impressão de papel;
- **Segurança** — chega ao cliente sem intermediação de terceiros e protegida por senha.

## Item 3 — Reativação/endereço da fatura impressa

Se o cliente insistir em receber a fatura impressa, confirme o endereço cadastrado.
- **Se divergente:** informe a necessidade de atualização do endereço.
- **Se correto:** acesse o aplicativo cartão `17.01.01.04.41.19`, marque "Com emissão de Extrato" e confirme — a fatura do próximo ciclo será impressa e entregue pelo correio no endereço do cliente.

Em ambos os casos, tente resolver o problema oferecendo o reenvio da fatura por e-mail (item 1).

## Item 4 — Cliente não recebe a fatura e quer saber o motivo

O operador consulta no SISALFA, cartão `17.01.01.01` — Faturas, na última coluna "Emit": haverá sinalização se a fatura foi emitida impressa (SIM), enviada por e-mail (EML), ou não emitida (NÃO). Para detalhes, selecione o mês com "M" (motivo da não impressão) e pressione Enter.

**Motivos comuns para o cliente não receber a fatura impressa, mesmo tendo optado por isso:**
- Endereço inválido;
- Débito automático em conta corrente com valor de fatura inferior a R$ 800,01 (o sistema inibe a emissão nesse caso; por e-mail, o cliente recebe qualquer valor);
- Saldo da fatura igual a zero ou credor;
- Modalidade sem fatura impressa;
- Optou por não impressão, ou há problemas cadastrais;
- Fatura em negociação no SISNEG;
- Cartão em cobrança terceirizada;
- Inconsistência do sistema — fatura não impressa.

Após solucionar a demanda sobre fatura não recebida, avise sempre que o cliente pode obter a fatura, inclusive de meses anteriores, pelo WhatsApp Alfa:
- Cadastrar o contato do WhatsApp Alfa;
- Escrever "Fatura do Cartão";
- Escrever "Código de Barras";
- (Há outras transações de cartão disponíveis no WhatsApp Alfa.)

## Item 6 — Consulta ao código de barras

**Procedimento obrigatório para todos os clientes:** faça a autenticação por Token, conforme rotina 50148:
- **Se houver sucesso**, o código de barras pode ser informado/ditado ao cliente.
- **Se não houver sucesso**, oriente o cliente a obter a fatura pelos canais descritos na rotina *(referência incompleta no documento original — provavelmente a mesma rotina 50182 citada anteriormente neste documento)*.

Informe ao cliente, conforme sua preferência, como obter o boleto pelos canais digitais:
- **Site institucional:** Correntistas: Cartões > Extrato > selecione o cartão > selecione a fatura > Operações financeiras (ícone de cartão, canto superior direito) > Boleto da Fatura. Não correntistas: Cartões > Cartões de Crédito > Extrato do Cartão de Crédito.
- **App Alfa:** Tela inicial > Cartões > selecione a imagem do cartão desejado > Meus cartões > Ver Faturas > selecione o mês da fatura fechada > Baixar fatura (rodapé); ou Menu > Cartões > Consultar fatura > Extrato da fatura > selecione cartão/período > Baixar fatura (rodapé).
- **WhatsApp Alfa:** cadastrar o contato; escrever "Fatura do Cartão"; selecionar "Código de Barras".
- **TAA:** o número do código de barras da fatura está no rodapé do extrato do cartão de crédito impresso na TAA.

Se o cliente não tiver fatura anterior ou não quiser usar outros canais, consulte o código de barras: `SISALFA: CARTAO > 17 > 01 > 01 > F9 > 22 > F8`. Atenção: informar mais 11 zeros no final do código, totalizando 14 dígitos no último campo. Informe também o valor e a data de vencimento da fatura.
