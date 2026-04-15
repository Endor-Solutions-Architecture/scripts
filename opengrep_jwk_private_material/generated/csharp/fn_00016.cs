using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"doM2IIxHe_gp","alg":"RS256","n":"wBMS6ipxviUKr0YBdw6LOXmog47EMJzmsgihjmO5faoS_OAF","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"doM2IIxHe_gp\",\"alg\":\"RS256\",\"n\":\"wBMS6ipxviUKr0YBdw6LOXmog47EMJzmsgihjmO5faoS_OAF\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}
