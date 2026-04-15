using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"EC","kid":"l3IgbukkN3xK","alg":"ES256","crv":"P-256","x":"QIlL4opVwuF1BMp1BfdLv_Yav_sLkPydnL6IvvRfG_Y","y":"accyaesitfWCq9C1gghqQPB3RF2F6nVWws77nrl_87U","d":"DmmNekzGagHgAONbCmVuqHIjqdtJDCJz_qWeGhsfbL3IPlIjJ7Bl6POdkVN0QW9s"}
    var jwk = "{\"kty\":\"EC\",\"kid\":\"l3IgbukkN3xK\",\"alg\":\"ES256\",\"crv\":\"P-256\",\"x\":\"QIlL4opVwuF1BMp1BfdLv_Yav_sLkPydnL6IvvRfG_Y\",\"y\":\"accyaesitfWCq9C1gghqQPB3RF2F6nVWws77nrl_87U\",\"d\":\"DmmNekzGagHgAONbCmVuqHIjqdtJDCJz_qWeGhsfbL3IPlIjJ7Bl6POdkVN0QW9s\"}";
    var key = new JsonWebKey(jwk);
  }
}
